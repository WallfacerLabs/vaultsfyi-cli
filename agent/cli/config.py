"""User-level configuration for the vaultsfyi CLI."""

from __future__ import annotations

import os
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

import tomli_w

DEFAULT_CONFIG: dict[str, Any] = {
    "wallet": {
        "name": "agent-treasury",
        "chain": "base",
        "vault_path": None,
        "ows_cli_path": None,
    },
    "network": {
        "rpc_url": "https://mainnet.base.org",
    },
    "vaults": {
        "api_url": "https://api.vaults.fyi",
        "api_key": None,
    },
    "strategy": {
        "network": "base",
        "asset": "USDC",
        "asset_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "min_deposit_usd": 0.10,
        "min_apy": 0.01,
        "min_tvl": 1_000_000,
        "apy_interval": "1day",
        "only_transactional": True,
        "vault_whitelist": [],
    },
    "display": {
        "decimals": 2,
        "position_retry_attempts": 3,
        "position_retry_delay": 5,
    },
}

ENV_MAP = {
    ("wallet", "name"): "OWS_WALLET",
    ("wallet", "chain"): "OWS_CHAIN",
    ("wallet", "vault_path"): "OWS_VAULT_PATH",
    ("wallet", "ows_cli_path"): "OWS_CLI_PATH",
    ("network", "rpc_url"): "BASE_RPC_URL",
    ("vaults", "api_key"): "VAULTS_API_KEY",
    ("vaults", "api_url"): "VAULTS_API_URL",
}


def config_dir() -> Path:
    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "vaultsfyi"
    return Path.home() / ".config" / "vaultsfyi"


def default_config_path() -> Path:
    return config_dir() / "config.toml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or default_config_path()
    cfg = deepcopy(DEFAULT_CONFIG)

    if path.exists():
        with path.open("rb") as fh:
            cfg = _deep_merge(cfg, tomllib.load(fh))

    apply_env_overrides(cfg)
    return cfg


def apply_env_overrides(cfg: dict[str, Any]) -> None:
    for (section, key), env_name in ENV_MAP.items():
        value = os.getenv(env_name)
        if value:
            cfg.setdefault(section, {})[key] = value


def _toml_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _toml_safe(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_toml_safe(v) for v in value]
    return value


def write_config(cfg: dict[str, Any], config_path: Path | None = None) -> Path:
    path = config_path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(_toml_safe(cfg)))
    return path


def agent_config(cfg: dict[str, Any]) -> dict[str, Any]:
    strategy = cfg["strategy"]
    display = cfg["display"]
    return {
        "vaults_api_url": cfg["vaults"].get("api_url", "https://api.vaults.fyi"),
        "network": strategy.get("network", "base"),
        "asset": strategy.get("asset", "USDC"),
        "asset_address": strategy.get("asset_address", DEFAULT_CONFIG["strategy"]["asset_address"]),
        "investment": {"min_deposit_usd": float(strategy.get("min_deposit_usd", 0.10))},
        "criteria": {
            "min_apy": float(strategy.get("min_apy", 0.01)),
            "min_tvl": float(strategy.get("min_tvl", 1_000_000)),
            "apy_interval": strategy.get("apy_interval", "1day"),
            "only_transactional": bool(strategy.get("only_transactional", True)),
        },
        "display": {
            "decimals": int(display.get("decimals", 2)),
            "position_retry_attempts": int(display.get("position_retry_attempts", 3)),
            "position_retry_delay": int(display.get("position_retry_delay", 5)),
        },
        "vault_whitelist": strategy.get("vault_whitelist", []),
    }


def export_env(cfg: dict[str, Any]) -> None:
    wallet = cfg["wallet"]
    network = cfg["network"]
    vaults = cfg["vaults"]

    values = {
        "OWS_WALLET": wallet.get("name"),
        "OWS_CHAIN": wallet.get("chain"),
        "OWS_VAULT_PATH": wallet.get("vault_path"),
        "OWS_CLI_PATH": wallet.get("ows_cli_path"),
        "BASE_RPC_URL": network.get("rpc_url"),
        "VAULTS_API_KEY": vaults.get("api_key"),
        "VAULTS_API_URL": vaults.get("api_url"),
    }
    for key, value in values.items():
        if value is not None and value != "":
            os.environ[key] = str(value)


def set_config_value(cfg: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    if len(parts) != 2:
        raise ValueError("config key must look like section.name, e.g. wallet.name")
    section, key = parts
    if section not in cfg:
        raise ValueError(f"unknown config section: {section}")
    cfg[section][key] = value
