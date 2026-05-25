"""
Vault filtering criteria
Client-side filtering for vault whitelist and diversification
"""

from typing import List


def _address_key(address: str | None) -> str:
    return (address or "").lower()


class VaultCriteria:
    """Handles client-side vault filtering"""

    def __init__(self, config: dict):
        """Initialize with configuration"""
        self.vault_whitelist = config.get('vault_whitelist', [])

    def apply_vault_whitelist(self, vaults: List[dict]) -> List[dict]:
        """
        Filter vaults by whitelist
        If whitelist is empty, return all vaults
        """
        if not self.vault_whitelist:
            return vaults

        filtered = []
        whitelist = {_address_key(address) for address in self.vault_whitelist}
        for vault in vaults:
            if _address_key(vault.get('vault_address')) in whitelist:
                filtered.append(vault)

        return filtered

    def exclude_existing_positions(
        self,
        vaults: List[dict],
        positions: List[dict]
    ) -> List[dict]:
        """
        Exclude vaults where user already has positions
        Enables automatic diversification
        """
        existing_vault_addresses = {_address_key(p.get('vault_address')) for p in positions}

        filtered = []
        for vault in vaults:
            if _address_key(vault.get('vault_address')) not in existing_vault_addresses:
                filtered.append(vault)

        return filtered
