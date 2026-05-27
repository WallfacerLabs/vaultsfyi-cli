"""Shared Vaults.fyi query parameter serialization."""

from __future__ import annotations

from typing import Any

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
        return bool_query_value(value, key)
    if key in NUMERIC_QUERY_FIELDS:
        return number_query_value(value, key)
    return value


def bool_query_value(value: Any, key: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in {"true", "yes", "1"}:
            return "true"
        if lower in {"false", "no", "0"}:
            return "false"
    raise ValueError(f"query parameter {key} must be boolean")


def number_query_value(value: Any, key: str) -> int | float:
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
