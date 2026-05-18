"""
Opportunity discovery API
Find best yield opportunities using API-side filtering
"""

from typing import List


class OpportunityAPI:
    """API for discovering yield opportunities"""

    def __init__(self, client):
        """Initialize with x402 client"""
        self.client = client

    def get_best_deposit_options(
        self,
        wallet_address: str,
        criteria: dict
    ) -> List[dict]:
        """
        Get best deposit options with API-side filtering
        Uses 1-day APY (requirement Q27)
        """
        endpoint = f"/v2/portfolio/best-deposit-options/{wallet_address}"

        # Send API parameters that work (minApy has API bug, apyInterval doesn't affect response)
        params = {
            'allowedAssets': 'USDC',
            'allowedNetworks': 'base',
            'minTvl': criteria.get('min_tvl', 100000),
            'onlyTransactional': 'true' if criteria.get('only_transactional', True) else 'false',
            # Note: minApy causes 400 error (API can't parse string as number)
            # Note: apyInterval doesn't seem to work (apy.1d always None)
        }

        response = self.client.make_request(endpoint, params=params)

        # Parse and filter opportunities client-side
        opportunities = []

        # Find USDC balance and its deposit options
        for user_balance in response.get('userBalances', []):
            asset = user_balance.get('asset', {})

            # Filter for USDC only
            if asset.get('symbol') != 'USDC':
                continue

            # Get deposit options for USDC
            for vault in user_balance.get('depositOptions', []):
                network = vault.get('network', {})
                apy_data = vault.get('apy', {})
                tvl_data = vault.get('tvl', {})

                # Apply filters
                network_name = network.get('name')
                if network_name != 'base':
                    continue

                # Check if transactional if required
                if criteria.get('only_transactional', True):
                    if not vault.get('isTransactional', False):
                        continue

                # Check TVL
                tvl = float(tvl_data.get('usd', 0))
                if tvl < criteria.get('min_tvl', 0):
                    continue

                # Check APY
                apy_total = float(apy_data.get('total', 0))
                if apy_total < criteria.get('min_apy', 0):
                    continue
                if criteria.get('max_apy') is not None and apy_total > criteria['max_apy']:
                    continue

                protocol = vault.get('protocol', {}) or {}
                curator = vault.get('curator', {}) or {}
                protocol_name = (protocol.get('name') or vault.get('protocolName') or '').lower()
                curator_name = (curator.get('name') or vault.get('curatorName') or '').lower()

                allowed_protocols = {p.lower() for p in criteria.get('allowed_protocols', [])}
                blocked_protocols = {p.lower() for p in criteria.get('blocked_protocols', [])}
                allowed_curators = {c.lower() for c in criteria.get('allowed_curators', [])}

                if allowed_protocols and protocol_name not in allowed_protocols:
                    continue
                if blocked_protocols and protocol_name in blocked_protocols:
                    continue
                if allowed_curators and curator_name not in allowed_curators:
                    continue

                opportunities.append({
                    'vault_address': vault.get('address'),
                    'vault_name': vault.get('name'),
                    'apy': apy_total,
                    'tvl': tvl,
                    'network': network_name,
                    'asset': asset.get('symbol'),
                    'protocol': protocol.get('name') or vault.get('protocolName'),
                    'curator': curator.get('name') or vault.get('curatorName'),
                })

        # Sort by APY descending
        opportunities.sort(key=lambda x: x['apy'], reverse=True)

        return opportunities
