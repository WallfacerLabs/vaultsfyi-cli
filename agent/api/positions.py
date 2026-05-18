"""
Position management API
Query user's current positions and idle assets
"""

from typing import List


def generate_nickname(vault_name: str) -> str:
    """Generate 10-char nickname from vault name (requirement Q10)"""
    return vault_name.replace(" ", "")[:10]


class PositionAPI:
    """API for querying positions and idle assets"""

    def __init__(self, client):
        """Initialize with x402 client"""
        self.client = client

    def get_positions(self, wallet_address: str) -> List[dict]:
        """
        Get user's vault positions
        Filters out zero-balance positions (requirement Q12)
        Generates nicknames (requirement Q10)
        """
        endpoint = f"/v2/portfolio/positions/{wallet_address}"
        params = {
            'allowedNetworks': 'base',
            'allowedAssets': 'USDC'
        }

        response = self.client.make_request(endpoint, params)

        # Parse positions (API returns in 'data' array)
        positions = []
        for position in response.get('data', []):
            # Get lpToken info (this is the vault token, represents the position value)
            lp_token = position.get('lpToken', {})
            balance_usd = float(lp_token.get('balanceUsd', 0))
            balance_native_lp = float(lp_token.get('balanceNative', 0))
            lp_decimals = int(lp_token.get('decimals', 18))

            # Filter out zero-balance positions (Q12)
            if balance_usd <= 0:
                continue

            # Generate nickname (Q10)
            vault_name = position.get('name', '')
            nickname = generate_nickname(vault_name)

            # Get APY
            apy_data = position.get('apy', {})
            apy_total = float(apy_data.get('total', 0))

            # Get network and asset info
            network = position.get('network', {})
            asset = position.get('asset', {})
            if network.get('name') != 'base' or asset.get('symbol') != 'USDC':
                continue

            # Calculate balance in LP tokens (for redemption)
            balance_lp_tokens = balance_native_lp / (10 ** lp_decimals)

            positions.append({
                'vault_address': position.get('address'),
                'vault_name': vault_name,
                'nickname': nickname,
                'asset': asset.get('symbol'),
                'apy': apy_total,
                'balance_usd': balance_usd,
                'balance_lp_tokens': balance_lp_tokens,  # LP tokens for redemption
                'lp_decimals': lp_decimals,
                'network': network.get('name'),
            })

        return positions

    def get_idle_assets(self, wallet_address: str) -> dict:
        """Get user's idle USDC balance"""
        endpoint = f"/v2/portfolio/idle-assets/{wallet_address}"
        params = {
            'allowedNetworks': 'base',
            'allowedAssets': 'USDC'
        }

        response = self.client.make_request(endpoint, params)

        # Find USDC balance (API returns data in 'data' array)
        for asset in response.get('data', []):
            if asset.get('symbol') == 'USDC':
                network = asset.get('network', {})
                if network.get('name') == 'base':
                    balance_native = float(asset.get('balanceNative', 0))
                    # USDC has 6 decimals
                    balance_tokens = balance_native / 1_000_000
                    return {
                        'usdc_balance': float(asset.get('balanceUsd', 0)),
                        'balance_tokens': balance_tokens,
                    }

        # No USDC found
        return {
            'usdc_balance': 0.0,
            'balance_tokens': 0.0,
        }
