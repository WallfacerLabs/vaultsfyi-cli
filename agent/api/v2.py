"""Low-level Vaults.fyi V2 API helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .client import X402Client

NUMERIC_QUERY_FIELDS = {
    "minApy",
    "maxApy",
    "minTvl",
    "maxTvl",
    "minVaultScore",
    "maxPerformanceFee",
    "maxManagementFee",
    "maxWithdrawalFee",
    "maxDepositFee",
    "minRemainingCapacity",
    "page",
    "perPage",
    "fromTimestamp",
    "toTimestamp",
    "amount",
    "maxVaultsPerAsset",
    "minUsdAssetValueThreshold",
}

BOOL_QUERY_FIELDS = {
    "onlyTransactional",
    "onlyAppFeatured",
    "allowCorrupted",
    "allowVaultsWithWarnings",
    "simulate",
    "onlyInstantDeposit",
    "onlyInstantRedeem",
    "onlyRewardsSupported",
}


def path_value(value: str) -> str:
    """Encode one path segment while allowing the API server to decode CAIP ids."""
    return quote(str(value), safe="")


def query_params(values: dict[str, Any]) -> dict[str, Any]:
    """Drop empty query values and coerce known typed query parameters."""
    params: dict[str, Any] = {}
    for key, value in values.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            normalized = [query_scalar(key, item) for item in value if item is not None and item != ""]
            if normalized:
                params[key] = normalized
            continue
        params[key] = query_scalar(key, value)
    return params


def query_scalar(key: str, value: Any) -> Any:
    if key in BOOL_QUERY_FIELDS:
        return _bool_value(value, key)
    if key in NUMERIC_QUERY_FIELDS:
        return _number_value(value, key)
    return value


def _bool_value(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in {"true", "yes", "1"}:
            return True
        if lower in {"false", "no", "0"}:
            return False
    raise ValueError(f"query parameter {key} must be boolean")


def _number_value(value: Any, key: str) -> int | float:
    if isinstance(value, bool):
        raise ValueError(f"query parameter {key} must be numeric")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        try:
            parsed = float(stripped)
        except ValueError as exc:
            raise ValueError(f"query parameter {key} must be numeric") from exc
        return int(parsed) if parsed.is_integer() and "." not in stripped and "e" not in stripped.lower() else parsed
    raise ValueError(f"query parameter {key} must be numeric")


class VaultsApiClient:
    """Thin client for Vaults.fyi V2 endpoints used by the CLI."""

    def __init__(self, base_url: str = "https://api.vaults.fyi", wallet=None):
        self.transport = X402Client(wallet=wallet, base_url=base_url)

    def request(self, endpoint: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        return self.transport.make_request(endpoint, query_params(params or {}), timeout=timeout)

    def get(self, endpoint: str, **params: Any) -> Any:
        return self.request(endpoint, params)
