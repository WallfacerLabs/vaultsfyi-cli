"""
Opportunity discovery API
Find best yield opportunities using API-side filtering
"""

from datetime import datetime, timezone
from typing import List

from agent.api.query import query_params


APY_INTERVAL_ALIASES = {
    '1day': ('1day', '1d', 'day'),
    '7day': ('7day', '7d', 'week'),
    '30day': ('30day', '30d', 'month'),
}

DETAILED_VAULT_QUERY_FIELDS = {
    'page': 'page',
    'per_page': 'perPage',
    'allowed_assets': 'allowedAssets',
    'disallowed_assets': 'disallowedAssets',
    'allowed_protocols': 'allowedProtocols',
    'disallowed_protocols': 'disallowedProtocols',
    'min_tvl': 'minTvl',
    'max_tvl': 'maxTvl',
    'min_vault_score': 'minVaultScore',
    'only_transactional': 'onlyTransactional',
    'only_app_featured': 'onlyAppFeatured',
    'allow_corrupted': 'allowCorrupted',
    'allow_vaults_with_warnings': 'allowVaultsWithWarnings',
    'allowed_networks': 'allowedNetworks',
    'disallowed_networks': 'disallowedNetworks',
    'apy_interval': 'apyInterval',
    'min_apy': 'minApy',
    'max_apy': 'maxApy',
    'tags': 'tags',
    'curators': 'curators',
    'sort_order': 'sortOrder',
    'sort_by': 'sortBy',
    'only_instant_deposit': 'onlyInstantDeposit',
    'only_instant_redeem': 'onlyInstantRedeem',
    'max_performance_fee': 'maxPerformanceFee',
    'max_management_fee': 'maxManagementFee',
    'max_withdrawal_fee': 'maxWithdrawalFee',
    'max_deposit_fee': 'maxDepositFee',
    'min_remaining_capacity': 'minRemainingCapacity',
    'only_rewards_supported': 'onlyRewardsSupported',
}

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


def _first_present(mapping: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return None


def _nested(mapping: dict, key: str) -> dict:
    value = mapping.get(key)
    return value if isinstance(value, dict) else {}


def _build_detailed_vault_params(criteria: dict) -> dict:
    params = {}
    for key, param_name in DETAILED_VAULT_QUERY_FIELDS.items():
        raw = criteria.get(key)
        if raw is not None and raw != [] and raw != "":
            params[param_name] = raw
    return query_params(params)


def _response_vaults(response: dict) -> list[dict]:
    data = response.get('data')
    if isinstance(data, list):
        return data
    if isinstance(response, list):
        return response

    # Backward-compatible parser for older tests and direct best-deposit payloads.
    vaults = []
    for user_balance in response.get('userBalances', []):
        asset = user_balance.get('asset', {})
        for vault in user_balance.get('depositOptions', []):
            if asset and 'asset' not in vault:
                vault = {**vault, 'asset': asset}
            vaults.append(vault)
    return vaults


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
        Get filtered deposit opportunities from detailed vault search.

        The wallet address is accepted for compatibility with callers, but
        candidate discovery is not wallet-specific. The deploy path computes
        the amount from the wallet's idle balance and validates transaction
        payload generation after selecting a vault.

        Uses the configured APY interval when the API returns it, otherwise
        falls back to total APY.
        """
        endpoint = "/v2/detailed-vaults"

        params = _build_detailed_vault_params(criteria)
        apy_interval = criteria.get('apy_interval', '1day')

        response = self.client.make_request(endpoint, params=params)
        detailed_response = isinstance(response, dict) and isinstance(response.get('data'), list)

        # Parse and filter opportunities client-side
        opportunities = []

        for vault in _response_vaults(response):
            network = _nested(vault, 'network')
            asset = _nested(vault, 'asset')
            protocol = _nested(vault, 'protocol')
            curator = _nested(vault, 'curator')
            tx_props = _nested(vault, 'transactionalProperties')
            fees = _nested(vault, 'fees')

            apy_data = vault.get('apy')
            if not isinstance(apy_data, dict):
                apy_data = {
                    '1day': _first_present(vault, ('apy1day', 'apy1d')),
                    '7day': _first_present(vault, ('apy7day', 'apy7d')),
                    '30day': _first_present(vault, ('apy30day', 'apy30d')),
                    '1hour': _first_present(vault, ('apy1hour', 'apy1h')),
                    'total': vault.get('apy'),
                }

            tvl_data = vault.get('tvl')
            if not isinstance(tvl_data, dict):
                tvl_data = {'usd': _first_present(vault, ('tvlUsd', 'tvlUSD', 'tvl'))}

            asset_symbol = (
                asset.get('symbol')
                or vault.get('assetSymbol')
                or vault.get('asset')
                or vault.get('underlyingAssetSymbol')
            )
            allowed_assets = _normalized_set(criteria.get('allowed_assets'))
            disallowed_assets = _normalized_set(criteria.get('disallowed_assets'))
            if allowed_assets and str(asset_symbol).lower() not in allowed_assets:
                continue
            if not allowed_assets and disallowed_assets and str(asset_symbol).lower() in disallowed_assets:
                continue

            network_name = network.get('name') or vault.get('network')
            network_caip = network.get('networkCaip') or vault.get('networkCaip')
            network_keys = {str(network_name).lower(), str(network_caip).lower()}
            allowed_networks = _normalized_set(criteria.get('allowed_networks'))
            disallowed_networks = _normalized_set(criteria.get('disallowed_networks'))
            if allowed_networks and network_keys.isdisjoint(allowed_networks):
                continue
            if not allowed_networks and disallowed_networks and not network_keys.isdisjoint(disallowed_networks):
                continue

            if _bool_or_none(criteria.get('only_transactional')) is not False:
                is_transactional = vault.get('isTransactional', tx_props.get('isTransactional'))
                if not is_transactional:
                    continue

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

            deposit_steps_type = _first_present(tx_props, ('depositStepsType', 'deposit_steps_type'))
            deposit_steps_type = deposit_steps_type or vault.get('depositStepsType')
            redeem_steps_type = _first_present(tx_props, ('redeemStepsType', 'redeem_steps_type'))
            redeem_steps_type = redeem_steps_type or vault.get('redeemStepsType')
            if _bool_or_none(criteria.get('only_instant_deposit')) is True:
                if deposit_steps_type != 'instant':
                    continue
            if _bool_or_none(criteria.get('only_instant_redeem')) is True:
                if redeem_steps_type != 'instant':
                    continue

            max_performance_fee = _float_or_none(criteria.get('max_performance_fee'))
            performance_fee = _float_or_none(_first_present(fees, ('performanceFee', 'performance_fee')) or vault.get('performanceFee'))
            if max_performance_fee is not None and performance_fee is not None and performance_fee > max_performance_fee:
                continue
            max_management_fee = _float_or_none(criteria.get('max_management_fee'))
            management_fee = _float_or_none(_first_present(fees, ('managementFee', 'management_fee')) or vault.get('managementFee'))
            if max_management_fee is not None and management_fee is not None and management_fee > max_management_fee:
                continue
            max_withdrawal_fee = _float_or_none(criteria.get('max_withdrawal_fee'))
            withdrawal_fee = _float_or_none(_first_present(fees, ('withdrawalFee', 'withdrawal_fee')) or vault.get('withdrawalFee'))
            if max_withdrawal_fee is not None and withdrawal_fee is not None and withdrawal_fee > max_withdrawal_fee:
                continue
            max_deposit_fee = _float_or_none(criteria.get('max_deposit_fee'))
            deposit_fee = _float_or_none(_first_present(fees, ('depositFee', 'deposit_fee')) or vault.get('depositFee'))
            if max_deposit_fee is not None and deposit_fee is not None and deposit_fee > max_deposit_fee:
                continue

            min_remaining_capacity = _float_or_none(criteria.get('min_remaining_capacity'))
            remaining_capacity = _float_or_none(vault.get('remainingCapacity'))
            if min_remaining_capacity is not None and remaining_capacity is not None and remaining_capacity < min_remaining_capacity:
                continue

            rewards_supported = tx_props.get('rewardsSupported', vault.get('rewardsSupported'))
            if _bool_or_none(criteria.get('only_rewards_supported')) is True:
                if rewards_supported is not True:
                    continue

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
                'vault_id': vault.get('vaultId') or vault.get('id'),
                'vault_address': vault.get('address') or vault.get('vaultAddress'),
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
                'deposit_steps_type': deposit_steps_type,
                'redeem_steps_type': redeem_steps_type,
                'performance_fee': performance_fee,
                'management_fee': management_fee,
                'withdrawal_fee': withdrawal_fee,
                'deposit_fee': deposit_fee,
                'remaining_capacity': remaining_capacity,
                'max_capacity': _float_or_none(vault.get('maxCapacity')),
                'rewards_supported': rewards_supported,
            })

        sort_by = criteria.get('sort_by')
        sort_order = (criteria.get('sort_order') or 'desc').lower()
        if sort_by:
            opportunities.sort(key=lambda item: _sort_key(item, sort_by), reverse=sort_order == 'desc')
        else:
            opportunities.sort(key=lambda x: x['apy'], reverse=True)

        if detailed_response:
            return opportunities
        return _page_results(opportunities, criteria)
