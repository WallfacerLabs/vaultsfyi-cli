"""Low-level Vaults.fyi V2 API helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .client import X402Client


def path_value(value: str) -> str:
    """Encode one path segment while allowing the API server to decode CAIP ids."""
    return quote(str(value), safe="")


def query_params(values: dict[str, Any]) -> dict[str, Any]:
    """Drop empty query values and normalize booleans for HTTP query strings."""
    params: dict[str, Any] = {}
    for key, value in values.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            normalized = [query_scalar(item) for item in value if item is not None and item != ""]
            if normalized:
                params[key] = normalized
            continue
        params[key] = query_scalar(value)
    return params


def query_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


class VaultsApiClient:
    """Thin client for Vaults.fyi V2 endpoints used by the CLI."""

    def __init__(self, base_url: str = "https://api.vaults.fyi", wallet=None):
        self.transport = X402Client(wallet=wallet, base_url=base_url)

    def request(self, endpoint: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        return self.transport.make_request(endpoint, query_params(params or {}), timeout=timeout)

    def get(self, endpoint: str, **params: Any) -> Any:
        return self.request(endpoint, params)
