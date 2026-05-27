"""Low-level Vaults.fyi V2 API helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .client import X402Client
from .query import query_params


def path_value(value: str) -> str:
    """Encode one path segment while allowing the API server to decode CAIP ids."""
    return quote(str(value), safe="")


class VaultsApiClient:
    """Thin client for Vaults.fyi V2 endpoints used by the CLI."""

    def __init__(self, base_url: str = "https://api.vaults.fyi", wallet=None):
        self.transport = X402Client(wallet=wallet, base_url=base_url)

    def request(self, endpoint: str, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        return self.transport.make_request(endpoint, params or {}, timeout=timeout)

    def get(self, endpoint: str, **params: Any) -> Any:
        return self.request(endpoint, params)
