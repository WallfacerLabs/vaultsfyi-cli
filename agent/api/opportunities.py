"""
Opportunity discovery API
Find best yield opportunities using API-side filtering
"""

from datetime import datetime, timezone
from typing import List


APY_INTERVAL_ALIASES = {
    '1day': ('1day', '1d', 'day'),
    '7day': ('7day', '7d', 'week'),
    '30day': ('30day', '30d', 'month'),
}

BEST_DEPOSIT_QUERY_FIELDS = {
    'allowed_assets': 'allowedAssets',
    'disallowed_assets': 'disallowedAssets',
    'allowed_protocols': 'allowedProtocols',
    'disallowed_protocols': 'disallowedProtocols',
    'min_tvl': 'minTvl',
    'min_vault_score': 'minVaultScore',
    'only_transactional': 'onlyTransactional',
    'only_app_featured': 'onlyAppFeatured',
    'allow_corrupted': 'allowCorrupted',
    'allow_vaults_with_warnings': 'allowVaultsWithWarnings',
    'allowed_networks': 'allowedNetworks',
    'disallowed_networks': 'disallowedNetworks',
    'apy_interval': 'apyInterval',
    'min_apy': 'minApy',
}

NUMERIC_QUERY_FIELDS = {'min_tvl', 'min_vault_score', 'min_apy'}


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _list_value(value) -> list:
    if value is None or value == '':
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str) and ',' in value:
        return [item.strip() for item in value.split(',') if item.strip()]
    return [value]


def _normalized_set(value) -> set[str]:
    return {str(item).lower() for item in _list_value(value)}


def _query_value(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return value


def _build_best_deposit_params(criteria: dict) -> dict:
    params = {}
    for key, param_name in BEST_DEPOSIT_QUERY_FIELDS.items():
        raw = criteria.get(key)
        if key in NUMERIC_QUERY_FIELDS:
            value = _float_or_none(raw)
        else:
            value = _query_value(raw)
        if value is not None and value != []:
            params[param_name] = value
    return params


def _apy_breakdown(apy_data: dict, apy_interval: str) -> dict:
    aliases = APY_INTERVAL_ALIASES.get(apy_interval, (apy_interval,))
    for key in aliases:
        value = apy_data.get(key)
        if isinstance(value, dict):
            return value
    return apy_data


def _select_apy(apy_data: dict, apy_interval: str) -> tuple[float, str]:
    """Prefer the configured APY interval when present, otherwise use total APY."""
    aliases = APY_INTERVAL_ALIASES.get(apy_interval, (apy_interval,))
    for key in aliases:
        raw_value = apy_data.get(key)
        if isinstance(raw_value, dict):
            value = _float_or_none(raw_value.get('total'))
        else:
            value = _float_or_none(raw_value)
        if value is not None:
            return value, key
    return _float_or_none(apy_data.get('total')) or 0.0, 'total'


def _bool_or_none(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower()
        if lower in {'true', 'yes', '1'}:
            return True
        if lower in {'false', 'no', '0'}:
            return False
        return None
    return bool(value)


def _is_withdrawable(vault: dict) -> bool | None:
    for key in ('isWithdrawable', 'withdrawable', 'canWithdraw', 'withdrawalsEnabled'):
        if key in vault:
            return _bool_or_none(vault.get(key))
    withdrawal = vault.get('withdrawal') or {}
    if isinstance(withdrawal, dict):
        for key in ('enabled', 'isEnabled', 'available'):
            if key in withdrawal:
                return _bool_or_none(withdrawal.get(key))
    return None


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def _vault_age_days(vault: dict) -> float | None:
    for key in ('ageDays', 'age_days'):
        value = _float_or_none(vault.get(key))
        if value is not None:
            return value
    for key in ('createdAt', 'created_at', 'deployedAt', 'deployed_at', 'inceptionDate', 'inception_date'):
        created_at = _parse_datetime(vault.get(key))
        if created_at is not None:
            return (datetime.now(timezone.utc) - created_at).total_seconds() / 86_400
    return None


def _is_incentive_heavy(apy_data: dict, apy_value: float) -> bool:
    incentive_apy = None
    for key in ('incentive', 'incentives', 'reward', 'rewards', 'boost'):
        incentive_apy = _float_or_none(apy_data.get(key))
        if incentive_apy is not None:
            break
    if incentive_apy is None or apy_value <= 0:
        return False
    base_apy = None
    for key in ('base', 'native', 'organic'):
        base_apy = _float_or_none(apy_data.get(key))
        if base_apy is not None:
            break
    if base_apy is not None and incentive_apy > base_apy:
        return True
    return incentive_apy / apy_value > 0.5


def _score_value(vault: dict, score_name: str) -> float | None:
    score = vault.get('score') or {}
    if isinstance(score, dict):
        value = _float_or_none(score.get(score_name))
        if value is not None:
            return value
    return _float_or_none(vault.get(score_name))


def _sort_key(opportunity: dict, sort_by: str):
    normalized = sort_by.replace('_', '').replace('-', '').lower()
    if normalized == 'tvl':
        return opportunity.get('tvl') or 0
    if normalized in {'apy1day', 'apy7day', 'apy30day', 'apy1hour'}:
        apy_intervals = opportunity.get('apy_intervals', {})
        interval = normalized.removeprefix('apy')
        return apy_intervals.get(interval) or opportunity.get('apy') or 0
    if normalized in {'vaultscore', 'score'}:
        return opportunity.get('vault_score') or 0
    return opportunity.get('apy') or 0


def _page_results(opportunities: list[dict], criteria: dict) -> list[dict]:
    page = criteria.get('page')
    per_page = criteria.get('per_page')
    if page is None or per_page is None:
        return opportunities
    start = int(page) * int(per_page)
    end = start + int(per_page)
    return opportunities[start:end]


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
        Uses the configured APY interval when the API returns it, otherwise
        falls back to total APY.
        """
        endpoint = f"/v2/portfolio/best-deposit-options/{wallet_address}"

        params = _build_best_deposit_params(criteria)
        apy_interval = criteria.get('apy_interval', '1day')

        response = self.client.make_request(endpoint, params=params)

        # Parse and filter opportunities client-side
        opportunities = []

        # Find USDC balance and its deposit options
        for user_balance in response.get('userBalances', []):
            asset = user_balance.get('asset', {})

            asset_symbol = asset.get('symbol')
            allowed_assets = _normalized_set(criteria.get('allowed_assets'))
            disallowed_assets = _normalized_set(criteria.get('disallowed_assets'))
            if allowed_assets and str(asset_symbol).lower() not in allowed_assets:
                continue
            if not allowed_assets and disallowed_assets and str(asset_symbol).lower() in disallowed_assets:
                continue

            # Get deposit options for USDC
            for vault in user_balance.get('depositOptions', []):
                network = vault.get('network', {})
                apy_data = vault.get('apy', {})
                tvl_data = vault.get('tvl', {})

                # Apply filters
                network_name = network.get('name')
                network_caip = network.get('networkCaip')
                network_keys = {str(network_name).lower(), str(network_caip).lower()}
                allowed_networks = _normalized_set(criteria.get('allowed_networks'))
                disallowed_networks = _normalized_set(criteria.get('disallowed_networks'))
                if allowed_networks and network_keys.isdisjoint(allowed_networks):
                    continue
                if not allowed_networks and disallowed_networks and not network_keys.isdisjoint(disallowed_networks):
                    continue

                # Check if transactional if required
                if _bool_or_none(criteria.get('only_transactional')) is not False:
                    if not vault.get('isTransactional', False):
                        continue

                # Check TVL
                tvl = _float_or_none(tvl_data.get('usd')) or 0.0
                min_tvl = _float_or_none(criteria.get('min_tvl')) or 0.0
                max_tvl = _float_or_none(criteria.get('max_tvl'))
                if tvl < min_tvl:
                    continue
                if max_tvl is not None and tvl > max_tvl:
                    continue

                vault_score = _score_value(vault, 'vaultScore')
                min_vault_score = _float_or_none(criteria.get('min_vault_score'))
                if min_vault_score is not None:
                    if vault_score is not None and vault_score < min_vault_score:
                        continue

                if _bool_or_none(criteria.get('only_app_featured')) is True:
                    if vault.get('isAppFeatured') is not True:
                        continue

                if _bool_or_none(criteria.get('allow_corrupted')) is False and vault.get('isCorrupted') is True:
                    continue

                allow_warnings = criteria.get('allow_vaults_with_warnings')
                if _bool_or_none(allow_warnings) is False:
                    if vault.get('warnings') or vault.get('flags'):
                        continue

                # Check APY
                apy_value, apy_source = _select_apy(apy_data, apy_interval)
                min_apy = _float_or_none(criteria.get('min_apy')) or 0.0
                max_apy = _float_or_none(criteria.get('max_apy'))
                if apy_value < min_apy:
                    continue
                if max_apy is not None and apy_value > max_apy:
                    continue
                if not criteria.get('allow_incentive_heavy_yield', True):
                    if _is_incentive_heavy(_apy_breakdown(apy_data, apy_interval), apy_value):
                        continue

                withdrawable = _is_withdrawable(vault)
                if criteria.get('require_withdrawable', False) and withdrawable is not True:
                    continue

                vault_age_days = _vault_age_days(vault)
                min_vault_age_days = criteria.get('min_vault_age_days')
                if min_vault_age_days is not None:
                    if vault_age_days is None or vault_age_days < float(min_vault_age_days):
                        continue

                # Deposit/redeem steps type filters (boolean, strict)
                if _bool_or_none(criteria.get('only_instant_deposit')) is True:
                    if vault.get('depositStepsType') != 'instant':
                        continue
                if _bool_or_none(criteria.get('only_instant_redeem')) is True:
                    if vault.get('redeemStepsType') != 'instant':
                        continue

                # Fee threshold filters (conservative: missing field passes)
                max_performance_fee = _float_or_none(criteria.get('max_performance_fee'))
                if max_performance_fee is not None:
                    perf_fee = _float_or_none(vault.get('performanceFee'))
                    if perf_fee is not None and perf_fee > max_performance_fee:
                        continue
                max_management_fee = _float_or_none(criteria.get('max_management_fee'))
                if max_management_fee is not None:
                    mgmt_fee = _float_or_none(vault.get('managementFee'))
                    if mgmt_fee is not None and mgmt_fee > max_management_fee:
                        continue
                max_withdrawal_fee = _float_or_none(criteria.get('max_withdrawal_fee'))
                if max_withdrawal_fee is not None:
                    wd_fee = _float_or_none(vault.get('withdrawalFee'))
                    if wd_fee is not None and wd_fee > max_withdrawal_fee:
                        continue
                max_deposit_fee = _float_or_none(criteria.get('max_deposit_fee'))
                if max_deposit_fee is not None:
                    dep_fee = _float_or_none(vault.get('depositFee'))
                    if dep_fee is not None and dep_fee > max_deposit_fee:
                        continue

                # Remaining capacity filter (conservative: missing field passes)
                min_remaining_capacity = _float_or_none(criteria.get('min_remaining_capacity'))
                if min_remaining_capacity is not None:
                    remaining_cap = _float_or_none(vault.get('remainingCapacity'))
                    if remaining_cap is not None and remaining_cap < min_remaining_capacity:
                        continue

                # Rewards supported filter (boolean, strict)
                if _bool_or_none(criteria.get('only_rewards_supported')) is True:
                    if vault.get('rewardsSupported') is not True:
                        continue

                protocol = vault.get('protocol', {}) or {}
                curator = vault.get('curator', {}) or {}
                protocol_name = (protocol.get('name') or vault.get('protocolName') or '').lower()
                curator_name = (curator.get('name') or vault.get('curatorName') or '').lower()
                vault_tags = {str(tag).lower() for tag in vault.get('tags', [])}

                allowed_protocols = _normalized_set(criteria.get('allowed_protocols'))
                blocked_protocols = (
                    _normalized_set(criteria.get('disallowed_protocols'))
                    or _normalized_set(criteria.get('blocked_protocols'))
                )
                allowed_curators = (
                    _normalized_set(criteria.get('curators'))
                    or _normalized_set(criteria.get('allowed_curators'))
                )
                required_tags = _normalized_set(criteria.get('tags'))

                if allowed_protocols and protocol_name not in allowed_protocols:
                    continue
                if blocked_protocols and protocol_name in blocked_protocols:
                    continue
                if allowed_curators and curator_name not in allowed_curators:
                    continue
                if required_tags and not required_tags.issubset(vault_tags):
                    continue

                apy_intervals = {}
                for interval in ('1day', '7day', '30day', '1hour'):
                    apy_intervals[interval] = _select_apy(apy_data, interval)[0]

                opportunities.append({
                    'vault_id': vault.get('vaultId'),
                    'vault_address': vault.get('address'),
                    'vault_name': vault.get('name'),
                    'apy': apy_value,
                    'apy_source': apy_source,
                    'apy_intervals': apy_intervals,
                    'tvl': tvl,
                    'vault_score': vault_score,
                    'is_app_featured': vault.get('isAppFeatured'),
                    'is_corrupted': vault.get('isCorrupted'),
                    'warnings': vault.get('warnings', []),
                    'flags': vault.get('flags', []),
                    'tags': vault.get('tags', []),
                    'withdrawable': withdrawable,
                    'vault_age_days': vault_age_days,
                    'network': network_name,
                    'asset': asset_symbol,
                    'protocol': protocol.get('name') or vault.get('protocolName'),
                    'curator': curator.get('name') or vault.get('curatorName'),
                    'deposit_steps_type': vault.get('depositStepsType'),
                    'redeem_steps_type': vault.get('redeemStepsType'),
                    'performance_fee': _float_or_none(vault.get('performanceFee')),
                    'management_fee': _float_or_none(vault.get('managementFee')),
                    'withdrawal_fee': _float_or_none(vault.get('withdrawalFee')),
                    'deposit_fee': _float_or_none(vault.get('depositFee')),
                    'remaining_capacity': _float_or_none(vault.get('remainingCapacity')),
                    'max_capacity': _float_or_none(vault.get('maxCapacity')),
                    'rewards_supported': vault.get('rewardsSupported'),
                })

        sort_by = criteria.get('sort_by')
        sort_order = (criteria.get('sort_order') or 'desc').lower()
        if sort_by:
            opportunities.sort(key=lambda item: _sort_key(item, sort_by), reverse=sort_order == 'desc')
        else:
            opportunities.sort(key=lambda x: x['apy'], reverse=True)

        return _page_results(opportunities, criteria)
