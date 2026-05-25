import pytest

from agent.api.opportunities import OpportunityAPI
from agent.api.transactions import TransactionAPI
from agent.api.v2 import query_params
from agent.strategy.criteria import VaultCriteria


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.last_endpoint = None
        self.last_params = None

    def make_request(self, endpoint, params=None):
        self.last_endpoint = endpoint
        self.last_params = params
        return self.response


def test_opportunities_prefer_configured_apy_interval_then_fallback_to_total():
    response = {
        "userBalances": [
            {
                "asset": {"symbol": "USDC"},
                "depositOptions": [
                    {
                        "address": "0xinterval",
                        "name": "Interval Vault",
                        "network": {"name": "base"},
                        "apy": {"1d": 0.06, "total": 0.02},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                    },
                    {
                        "address": "0xfallback",
                        "name": "Fallback Vault",
                        "network": {"name": "base"},
                        "apy": {"total": 0.05},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                    },
                ],
            }
        ]
    }

    opportunities = OpportunityAPI(FakeClient(response)).get_best_deposit_options(
        "0xwallet",
        {"min_apy": 0.01, "min_tvl": 1_000_000, "only_transactional": True, "apy_interval": "1day"},
    )

    assert [item["vault_address"] for item in opportunities] == ["0xinterval", "0xfallback"]
    assert opportunities[0]["apy"] == 0.06
    assert opportunities[0]["apy_source"] == "1d"
    assert opportunities[1]["apy_source"] == "total"


def test_opportunities_apply_risk_filters_when_requested():
    response = {
        "userBalances": [
            {
                "asset": {"symbol": "USDC"},
                "depositOptions": [
                    {
                        "address": "0xsafe",
                        "name": "Safe Vault",
                        "network": {"name": "base"},
                        "apy": {"total": 0.04, "base": 0.035, "reward": 0.005},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                        "isWithdrawable": True,
                        "ageDays": 30,
                    },
                    {
                        "address": "0xyoung",
                        "name": "Young Vault",
                        "network": {"name": "base"},
                        "apy": {"total": 0.04},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                        "isWithdrawable": True,
                        "ageDays": 2,
                    },
                    {
                        "address": "0xincentive",
                        "name": "Incentive Vault",
                        "network": {"name": "base"},
                        "apy": {"total": 0.10, "base": 0.02, "reward": 0.08},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                        "isWithdrawable": True,
                        "ageDays": 30,
                    },
                    {
                        "address": "0xlocked",
                        "name": "Locked Vault",
                        "network": {"name": "base"},
                        "apy": {"total": 0.04},
                        "tvl": {"usd": 2_000_000},
                        "isTransactional": True,
                        "isWithdrawable": False,
                        "ageDays": 30,
                    },
                ],
            }
        ]
    }

    opportunities = OpportunityAPI(FakeClient(response)).get_best_deposit_options(
        "0xwallet",
        {
            "min_apy": 0.01,
            "min_tvl": 1_000_000,
            "only_transactional": True,
            "require_withdrawable": True,
            "min_vault_age_days": 7,
            "allow_incentive_heavy_yield": False,
        },
    )

    assert [item["vault_address"] for item in opportunities] == ["0xsafe"]


def test_opportunities_send_supported_detailed_vault_filters_as_query_params():
    client = FakeClient({"userBalances": []})

    OpportunityAPI(client).get_best_deposit_options(
        "0xwallet",
        {
            "allowed_assets": ["USDC", "WETH"],
            "disallowed_assets": ["DAI"],
            "allowed_protocols": ["morpho"],
            "disallowed_protocols": ["aave"],
            "min_tvl": 1_000_000,
            "min_vault_score": 8,
            "only_transactional": True,
            "only_app_featured": True,
            "allow_corrupted": False,
            "allow_vaults_with_warnings": False,
            "allowed_networks": ["base", "eip155:1"],
            "disallowed_networks": ["polygon"],
            "apy_interval": "7day",
            "min_apy": 0.02,
            "max_tvl": 5_000_000,
            "max_apy": 0.20,
            "tags": ["stablecoin"],
            "curators": ["steakhouse"],
            "sort_by": "apy7day",
            "sort_order": "desc",
        },
    )

    assert client.last_params == {
        "allowedAssets": ["USDC", "WETH"],
        "disallowedAssets": ["DAI"],
        "allowedProtocols": ["morpho"],
        "disallowedProtocols": ["aave"],
        "minTvl": 1_000_000,
        "minVaultScore": 8,
        "onlyTransactional": "true",
        "onlyAppFeatured": "true",
        "allowCorrupted": "false",
        "allowVaultsWithWarnings": "false",
        "allowedNetworks": ["base", "eip155:1"],
        "disallowedNetworks": ["polygon"],
        "apyInterval": "7day",
        "minApy": 0.02,
    }


def test_opportunities_apply_detailed_only_filters_sort_and_page_locally():
    response = {
        "userBalances": [
            {
                "asset": {"symbol": "USDC"},
                "depositOptions": [
                    {
                        "vaultId": "vault-a",
                        "address": "0xa",
                        "name": "A",
                        "network": {"name": "base", "networkCaip": "eip155:8453"},
                        "protocol": {"name": "morpho"},
                        "curator": {"name": "steakhouse"},
                        "tags": ["stablecoin", "blue-chip"],
                        "apy": {
                            "7day": {"base": 0.025, "reward": 0.005, "total": 0.03},
                            "30day": {"base": 0.04, "reward": 0.01, "total": 0.05},
                        },
                        "tvl": {"usd": "500000"},
                        "score": {"vaultScore": 9},
                        "isTransactional": True,
                        "isAppFeatured": True,
                        "isCorrupted": False,
                        "warnings": [],
                        "flags": [],
                    },
                    {
                        "vaultId": "vault-b",
                        "address": "0xb",
                        "name": "B",
                        "network": {"name": "base", "networkCaip": "eip155:8453"},
                        "protocol": {"name": "morpho"},
                        "curator": {"name": "steakhouse"},
                        "tags": ["stablecoin"],
                        "apy": {
                            "7day": {"base": 0.03, "reward": 0.005, "total": 0.035},
                            "30day": {"base": 0.06, "reward": 0.01, "total": 0.07},
                        },
                        "tvl": {"usd": "800000"},
                        "score": {"vaultScore": 10},
                        "isTransactional": True,
                        "isAppFeatured": True,
                        "isCorrupted": False,
                        "warnings": [],
                        "flags": [],
                    },
                    {
                        "address": "0xwrongtag",
                        "name": "Wrong Tag",
                        "network": {"name": "base"},
                        "protocol": {"name": "morpho"},
                        "curator": {"name": "steakhouse"},
                        "tags": ["volatile"],
                        "apy": {"7day": {"total": 0.04}, "30day": {"total": 0.08}},
                        "tvl": {"usd": "700000"},
                        "score": {"vaultScore": 10},
                        "isTransactional": True,
                        "isAppFeatured": True,
                    },
                    {
                        "address": "0xwarning",
                        "name": "Warning",
                        "network": {"name": "base"},
                        "protocol": {"name": "morpho"},
                        "curator": {"name": "steakhouse"},
                        "tags": ["stablecoin"],
                        "apy": {"7day": {"total": 0.04}, "30day": {"total": 0.08}},
                        "tvl": {"usd": "700000"},
                        "score": {"vaultScore": 10},
                        "isTransactional": True,
                        "isAppFeatured": True,
                        "warnings": ["review me"],
                    },
                    {
                        "address": "0xlarge",
                        "name": "Large",
                        "network": {"name": "base"},
                        "protocol": {"name": "morpho"},
                        "curator": {"name": "steakhouse"},
                        "tags": ["stablecoin"],
                        "apy": {"7day": {"total": 0.04}, "30day": {"total": 0.08}},
                        "tvl": {"usd": "10000000"},
                        "score": {"vaultScore": 10},
                        "isTransactional": True,
                        "isAppFeatured": True,
                    },
                ],
            }
        ]
    }

    opportunities = OpportunityAPI(FakeClient(response)).get_best_deposit_options(
        "0xwallet",
        {
            "allowed_assets": "USDC",
            "allowed_networks": "base",
            "allowed_protocols": "morpho",
            "curators": "steakhouse",
            "tags": "stablecoin",
            "min_apy": 0.01,
            "max_apy": 0.04,
            "min_tvl": 100_000,
            "max_tvl": 900_000,
            "min_vault_score": 8,
            "only_transactional": True,
            "only_app_featured": True,
            "allow_corrupted": False,
            "allow_vaults_with_warnings": False,
            "apy_interval": "7day",
            "sort_by": "apy30day",
            "sort_order": "desc",
            "page": 0,
            "per_page": 2,
        },
    )

    assert [item["vault_address"] for item in opportunities] == ["0xb", "0xa"]
    assert opportunities[0]["apy_intervals"]["30day"] == 0.07


def test_redeem_transaction_uses_only_default_action():
    response = {
        "actions": [
            {"tx": {"to": "0xfirst", "data": "0xaaa", "value": "0"}},
            {"tx": {"to": "0xsecond", "data": "0xbbb", "value": "0"}},
        ]
    }

    transactions = TransactionAPI(FakeClient(response)).generate_redeem_tx(
        "0xwallet",
        "0xvault",
        1.0,
        18,
        "0xasset",
    )

    assert transactions == [{"to": "0xfirst", "data": "0xaaa", "value": "0"}]


def test_transaction_generation_rejects_empty_action_sets():
    api = TransactionAPI(FakeClient({"actions": []}))

    with pytest.raises(ValueError, match="no deposit transaction actions"):
        api.generate_deposit_tx("0xwallet", "0xvault", 1.0, "0xasset")

    with pytest.raises(ValueError, match="no redeem transaction actions"):
        api.generate_redeem_tx("0xwallet", "0xvault", 1.0, 18, "0xasset")


def test_transaction_generation_rejects_malformed_actions():
    api = TransactionAPI(FakeClient({"actions": [{"tx": {"to": "0xvault"}}]}))

    with pytest.raises(ValueError, match="without tx.to or tx.data"):
        api.generate_deposit_tx("0xwallet", "0xvault", 1.0, "0xasset")


def test_vault_criteria_compares_addresses_case_insensitively():
    criteria = VaultCriteria({"vault_whitelist": ["0xabc"]})

    assert criteria.apply_vault_whitelist([{"vault_address": "0xABC"}]) == [{"vault_address": "0xABC"}]
    assert criteria.exclude_existing_positions(
        [{"vault_address": "0xABC"}, {"vault_address": "0xDEF"}],
        [{"vault_address": "0xabc"}],
    ) == [{"vault_address": "0xDEF"}]


def test_v2_query_params_normalize_without_losing_arrays_or_false_values():
    assert query_params(
        {
            "page": 0,
            "empty": "",
            "missing": None,
            "enabled": True,
            "disabled": False,
            "items": ["USDC", "", None, "WETH"],
        }
    ) == {
        "page": 0,
        "enabled": "true",
        "disabled": "false",
        "items": ["USDC", "WETH"],
    }
