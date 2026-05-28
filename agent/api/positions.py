"""
Position management API
Query user's current positions and idle assets
"""

import math
from typing import Any, List


DEFAULT_POSITION_DUST_USD = 0.01


def generate_nickname(vault_name: str) -> str:
    """Generate 10-char nickname from vault name (requirement Q10)"""
    return vault_name.replace(" ", "")[:10]


class PositionAPI:
    """API for querying positions and idle assets"""

    def __init__(self, client):
        """Initialize with x402 client"""
        self.client = client

    def get_positions(
        self,
        wallet_address: str,
        *,
        min_balance_usd: float = DEFAULT_POSITION_DUST_USD,
        reference_idle_usd: float | None = None,
        consistency_retries: int = 2,
    ) -> List[dict]:
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

        attempts = max(1, int(consistency_retries) + 1)
        for attempt in range(attempts):
            response = self.client.make_request(endpoint, params)
            positions, reported_idle_usd = self._parse_positions_response(response, min_balance_usd)
            if (
                reference_idle_usd is not None
                and not positions
                and attempt < attempts - 1
            ):
                continue
            if not _idle_snapshot_conflicts(reference_idle_usd, reported_idle_usd, positions):
                return positions

        # If the positions endpoint keeps returning rows from a different
        # portfolio snapshot than idle-assets, or repeatedly returns empty
        # during indexing lag, avoid double counting or inventing positions.
        return []

    def _parse_positions_response(self, response: dict, min_balance_usd: float) -> tuple[list[dict], float | None]:
        """Normalize raw portfolio positions and retain embedded idle USD if present."""
        dust_usd = max(0.0, float(min_balance_usd))

        # Parse positions (API returns in 'data' array)
        positions = []
        reported_idle_values = []
        for position in response.get('data', []):
            # Get lpToken info (this is the vault token, represents the position value)
            lp_token = position.get('lpToken', {})
            balance_usd = _safe_float(lp_token.get('balanceUsd'), 0.0)
            balance_native_lp = _safe_float(lp_token.get('balanceNative'), 0.0)
            lp_decimals = int(lp_token.get('decimals') or 18)

            raw_asset = position.get('asset', {})
            raw_asset = raw_asset if isinstance(raw_asset, dict) else {}
            reported_idle_usd = _safe_float(raw_asset.get('balanceUsd'), math.nan)
            if math.isfinite(reported_idle_usd):
                reported_idle_values.append(reported_idle_usd)

            # Filter out zero and dust positions (Q12 plus execution dust guard).
            if balance_usd < dust_usd:
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

        reported_idle_usd = max(reported_idle_values) if reported_idle_values else None
        return positions, reported_idle_usd

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


def _safe_float(value: Any, default: float) -> float:
    if value in (None, "", []):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _idle_snapshot_conflicts(
    reference_idle_usd: float | None,
    reported_idle_usd: float | None,
    positions: list[dict],
) -> bool:
    if not positions or reference_idle_usd is None:
        return False
    try:
        reference = float(reference_idle_usd)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(reference):
        return False
    if reported_idle_usd is None:
        return False
    tolerance = max(DEFAULT_POSITION_DUST_USD, abs(reference) * 0.005)
    return abs(float(reported_idle_usd) - reference) > tolerance
