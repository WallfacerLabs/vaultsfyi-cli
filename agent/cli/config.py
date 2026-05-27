"""User-level and per-agent configuration for the vaultsfyi CLI."""

from __future__ import annotations

import os
import tomllib
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

import tomli_w
from dotenv import load_dotenv

DETAILED_VAULT_FILTER_DEFAULTS: dict[str, Any] = {
    "page": None,
    "per_page": None,
    "allowed_assets": [],
    "disallowed_assets": [],
    "allowed_protocols": [],
    "disallowed_protocols": [],
    "min_tvl": 1_000_000,
    "max_tvl": None,
    "min_apy": 0.01,
    "max_apy": None,
    "min_vault_score": None,
    "only_transactional": True,
    "only_app_featured": None,
    "allow_corrupted": False,
    "allow_vaults_with_warnings": None,
    "allowed_networks": [],
    "disallowed_networks": [],
    "tags": [],
    "curators": [],
    "sort_order": None,
    "sort_by": None,
}

DEFAULT_CONFIG: dict[str, Any] = {
    "agent": {
        "name": "default",
        "mode": "dry-run",  # dry-run | paper | live
        "preference": None,
        "max_deploy_usd": None,
        "max_position_pct": None,
    },
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
        "apy_interval": "1day",
        "vault_whitelist": [],
        "blocked_protocols": [],
        "allowed_curators": [],
        **DETAILED_VAULT_FILTER_DEFAULTS,
    },
    "risk": {
        "max_single_vault_usd": None,
        "require_withdrawable": False,
        "min_vault_age_days": None,
        "allow_incentive_heavy_yield": True,
    },
    "execution": {
        "deploy_percent": 10.0,
        "require_confirmation": True,
        "slippage_bps": 50,
        "cooldown_after_tx": "10m",
    },
    "decision": {
        "min_net_gain_usd": 1.0,
        "max_breakeven_days": 30,
        "min_apy_improvement": 0.01,
        "max_rebalance_pct": 50,
        "allow_partial_rebalance": True,
        "prefer_hold_if_uncertain": True,
        "eth_usd_price": 3000.0,
        "deposit_gas_units": 350000,
        "redeem_gas_units": 500000,
    },
    "preferences": {},
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


def agents_dir() -> Path:
    return config_dir() / "agents"


def agent_config_path(agent_name: str) -> Path:
    return agents_dir() / f"{agent_name}.toml"


def state_dir(agent_name: str | None = None) -> Path:
    root = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "vaultsfyi"
    return root / "agents" / agent_name if agent_name else root


def logs_dir(agent_name: str | None = None) -> Path:
    root = state_dir() / "logs"
    return root / agent_name if agent_name else root


def locks_dir() -> Path:
    return state_dir() / "locks"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(config_path: Path | None = None, agent_name: str | None = None) -> dict[str, Any]:
    load_dotenv(Path.cwd() / ".env", override=False)
    path = config_path or default_config_path()
    cfg = deepcopy(DEFAULT_CONFIG)

    if path.exists():
        cfg = _deep_merge(cfg, load_toml(path))

    if agent_name:
        profile_path = agent_config_path(agent_name)
        if not profile_path.exists():
            raise ValueError(f"agent profile '{agent_name}' does not exist at {profile_path}")
        profile_cfg = load_toml(profile_path)
        cfg = _deep_merge(cfg, profile_cfg)
        cfg.setdefault("agent", {})["name"] = agent_name
        if "preference" not in profile_cfg.get("agent", {}):
            cfg["agent"]["preference"] = None
        cfg["agent"]["profile_path"] = str(profile_path)
    else:
        cfg.setdefault("agent", {})["name"] = cfg.get("agent", {}).get("name") or "default"

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


def write_toml_path(path: Path, cfg: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(_toml_safe(cfg)))
    return path


def write_agent_profile(agent_name: str, cfg: dict[str, Any]) -> Path:
    path = agent_config_path(agent_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(_toml_safe(cfg)))
    return path


def set_config_file_value(path: Path, dotted_key: str, value: Any) -> Path:
    cfg = load_toml(path) if path.exists() else deepcopy(DEFAULT_CONFIG)
    set_config_value(cfg, dotted_key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(_toml_safe(cfg)))
    return path


def list_agent_profiles() -> list[dict[str, Any]]:
    if not agents_dir().exists():
        return []
    rows = []
    for path in sorted(agents_dir().glob("*.toml")):
        try:
            cfg = load_toml(path)
        except Exception:
            cfg = {}
        rows.append({
            "name": path.stem,
            "wallet": cfg.get("wallet", {}).get("name", ""),
            "mode": cfg.get("agent", {}).get("mode", ""),
            "preference": cfg.get("agent", {}).get("preference"),
            "path": str(path),
        })
    return rows


def new_preference() -> dict[str, Any]:
    return {}


def list_preferences(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    def preference_value(pref: dict[str, Any], key: str, alias: str) -> Any:
        return pref.get(key) if pref.get(key) is not None else pref.get(alias)

    return [
        {
            "name": name,
            "min_apy": pref.get("min_apy"),
            "max_apy": pref.get("max_apy"),
            "min_tvl": pref.get("min_tvl"),
            "max_tvl": pref.get("max_tvl"),
            "min_vault_score": pref.get("min_vault_score"),
            "only_transactional": pref.get("only_transactional", True),
            "only_app_featured": pref.get("only_app_featured"),
            "allowed_assets": pref.get("allowed_assets") or pref.get("asset"),
            "allowed_networks": pref.get("allowed_networks") or pref.get("network"),
            "allowed_protocols": pref.get("allowed_protocols"),
            "disallowed_protocols": pref.get("disallowed_protocols") or pref.get("blocked_protocols"),
            "tags": pref.get("tags"),
            "curators": pref.get("curators") or pref.get("allowed_curators"),
            "bucket_max_pct": preference_value(pref, "bucket_max_pct", "max_portfolio_pct"),
            "bucket_tolerance_pct": preference_value(pref, "bucket_tolerance_pct", "tolerance_pct"),
        }
        for name, pref in sorted(cfg.get("preferences", {}).items())
    ]


def new_agent_profile(agent_name: str, wallet_name: str | None = None, mode: str = "dry-run") -> dict[str, Any]:
    if mode not in {"dry-run", "paper", "live"}:
        raise ValueError("mode must be dry-run, paper, or live")
    return {
        "agent": {
            "name": agent_name,
            "mode": mode,
            "preference": None,
            "max_deploy_usd": None,
            "max_position_pct": None,
        },
        "wallet": {
            "name": wallet_name or agent_name,
            "chain": "base",
        },
        "strategy": deepcopy(DEFAULT_CONFIG["strategy"]),
        "risk": deepcopy(DEFAULT_CONFIG["risk"]),
        "execution": deepcopy(DEFAULT_CONFIG["execution"]),
    }


def agent_config(cfg: dict[str, Any]) -> dict[str, Any]:
    strategy = cfg["strategy"]
    risk = cfg.get("risk", {})
    display = cfg["display"]

    def list_value(value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (tuple, set)):
            return list(value)
        if isinstance(value, str) and "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    allowed_assets = list_value(strategy.get("allowed_assets")) or [strategy.get("asset", "USDC")]
    allowed_networks = list_value(strategy.get("allowed_networks")) or [strategy.get("network", "base")]
    criteria = {
        "page": strategy.get("page"),
        "per_page": strategy.get("per_page"),
        "allowed_assets": allowed_assets,
        "disallowed_assets": list_value(strategy.get("disallowed_assets")),
        "allowed_networks": allowed_networks,
        "disallowed_networks": list_value(strategy.get("disallowed_networks")),
        "min_apy": float(strategy.get("min_apy", 0.01)),
        "min_tvl": float(strategy.get("min_tvl", 1_000_000)),
        "apy_interval": strategy.get("apy_interval", "1day"),
        "only_transactional": bool(strategy.get("only_transactional", True)),
        "allowed_protocols": list_value(strategy.get("allowed_protocols")),
        "disallowed_protocols": list_value(strategy.get("disallowed_protocols")) or list_value(strategy.get("blocked_protocols")),
        "blocked_protocols": list_value(strategy.get("blocked_protocols")),
        "curators": list_value(strategy.get("curators")) or list_value(strategy.get("allowed_curators")),
        "allowed_curators": list_value(strategy.get("allowed_curators")),
        "tags": list_value(strategy.get("tags")),
        "sort_order": strategy.get("sort_order"),
        "sort_by": strategy.get("sort_by"),
        "min_vault_score": strategy.get("min_vault_score"),
        "only_app_featured": strategy.get("only_app_featured"),
        "allow_corrupted": strategy.get("allow_corrupted"),
        "allow_vaults_with_warnings": strategy.get("allow_vaults_with_warnings"),
        "require_withdrawable": bool(risk.get("require_withdrawable", False)),
        "min_vault_age_days": risk.get("min_vault_age_days"),
        "allow_incentive_heavy_yield": bool(risk.get("allow_incentive_heavy_yield", True)),
    }
    if strategy.get("max_apy") is not None:
        criteria["max_apy"] = float(strategy["max_apy"])
    if strategy.get("max_tvl") is not None:
        criteria["max_tvl"] = float(strategy["max_tvl"])
    return {
        "vaults_api_url": cfg["vaults"].get("api_url", "https://api.vaults.fyi"),
        "network": strategy.get("network", "base"),
        "asset": strategy.get("asset", "USDC"),
        "asset_address": strategy.get("asset_address", DEFAULT_CONFIG["strategy"]["asset_address"]),
        "investment": {"min_deposit_usd": float(strategy.get("min_deposit_usd", 0.10))},
        "criteria": criteria,
        "display": {
            "decimals": int(display.get("decimals", 2)),
            "position_retry_attempts": int(display.get("position_retry_attempts", 3)),
            "position_retry_delay": int(display.get("position_retry_delay", 5)),
        },
        "vault_whitelist": strategy.get("vault_whitelist", []),
    }


def _env_values(cfg: dict[str, Any]) -> dict[str, Any]:
    wallet = cfg["wallet"]
    network = cfg["network"]
    vaults = cfg["vaults"]

    return {
        "OWS_WALLET": wallet.get("name"),
        "OWS_CHAIN": wallet.get("chain"),
        "OWS_VAULT_PATH": wallet.get("vault_path"),
        "OWS_CLI_PATH": wallet.get("ows_cli_path"),
        "BASE_RPC_URL": network.get("rpc_url"),
        "VAULTS_API_KEY": vaults.get("api_key"),
        "VAULTS_API_URL": vaults.get("api_url"),
    }


def export_env(cfg: dict[str, Any]) -> None:
    for key, value in _env_values(cfg).items():
        if value is not None and value != "":
            os.environ[key] = str(value)
        else:
            os.environ.pop(key, None)


@contextmanager
def exported_env(cfg: dict[str, Any]):
    keys = _env_values(cfg).keys()
    missing = object()
    previous = {key: os.environ.get(key, missing) for key in keys}
    export_env(cfg)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def set_config_value(cfg: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    if len(parts) != 2:
        raise ValueError("config key must look like section.name, e.g. wallet.name")
    section, key = parts
    if section not in cfg:
        raise ValueError(f"unknown config section: {section}")
    cfg[section][key] = value


def parse_config_value(value: str) -> Any:
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"none", "null"}:
        return None
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def sanitize_config(cfg: dict[str, Any]) -> dict[str, Any]:
    sanitized = deepcopy(cfg)
    if sanitized.get("vaults", {}).get("api_key"):
        sanitized["vaults"]["api_key"] = "***"
    return sanitized
