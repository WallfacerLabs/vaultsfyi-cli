"""
OWS wallet module.

This project uses Open Wallet Standard (https://openwallet.sh/) for wallet
storage and signing. Private keys are never loaded from .env and are never
exposed to the agent process.
"""

import os
from typing import Any

from dotenv import load_dotenv
from ows import get_wallet


DEFAULT_WALLET_NAME = "agent-treasury"
DEFAULT_CHAIN = "base"
EVM_ACCOUNT_PREFIX = "eip155:"


class Wallet:
    """OWS-backed wallet handle.

    The wallet is resolved from the local OWS vault, normally ~/.ows/.
    Configure it with:
      - OWS_WALLET: wallet name or UUID (default: agent-treasury)
      - OWS_PASSPHRASE: wallet passphrase or scoped OWS API token
      - OWS_VAULT_PATH: optional custom vault path for tests/sandboxes
      - OWS_CHAIN: signing chain alias/CAIP-2 ID (default: base)
    """

    def __init__(self, name: str | None = None, chain: str | None = None):
        load_dotenv()

        self.name = name or os.getenv("OWS_WALLET", DEFAULT_WALLET_NAME)
        self.chain = chain or os.getenv("OWS_CHAIN", DEFAULT_CHAIN)
        self.passphrase = os.getenv("OWS_PASSPHRASE")
        self.vault_path = os.getenv("OWS_VAULT_PATH") or None

        try:
            self.wallet_info: dict[str, Any] = get_wallet(self.name, vault_path_opt=self.vault_path)
        except Exception as exc:
            raise ValueError(
                f"OWS wallet '{self.name}' was not found. Create one with "
                f"`vaultsfyi wallet create --name {self.name}` "
                "or import one with the `ows wallet import` CLI."
            ) from exc

        self.id = self.wallet_info["id"]
        self.address = self._evm_address()

    def _evm_address(self) -> str:
        for account in self.wallet_info.get("accounts", []):
            if account.get("chain_id", "").startswith(EVM_ACCOUNT_PREFIX):
                return account["address"]
        raise ValueError(f"OWS wallet '{self.name}' does not contain an EVM account")

    def get_address(self) -> str:
        """Return the EVM wallet address."""
        return self.address

    def __repr__(self):
        return f"Wallet(name={self.name}, address={self.address})"
