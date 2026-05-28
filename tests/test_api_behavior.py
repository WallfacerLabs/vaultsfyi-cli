import pytest

from agent.api.client import X402Client
from agent.api.opportunities import OpportunityAPI
from agent.api.positions import PositionAPI
from agent.api.transactions import TransactionAPI
from agent.core.executor import TransactionExecutor
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


class SequenceFakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def make_request(self, endpoint, params=None):
        self.calls.append((endpoint, params))
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def _position_response(balance_usd, *, asset_balance_usd="59.96", balance_native="1000000"):
    return {
        "data": [
            {
                "address": "0xvault",
                "name": "Vault",
                "network": {"name": "base"},
                "asset": {"symbol": "USDC", "balanceUsd": asset_balance_usd},
                "apy": {"total": 0.05},
                "lpToken": {
                    "balanceUsd": str(balance_usd),
                    "balanceNative": str(balance_native),
                    "decimals": 6,
                },
            }
        ]
    }


def test_positions_ignore_dust_balances():
    positions = PositionAPI(FakeClient(_position_response("0.009"))).get_positions(
        "0xwallet",
        min_balance_usd=0.01,
    )

    assert positions == []


def test_positions_retry_stale_snapshot_against_reference_idle():
    stale = _position_response("35.98", asset_balance_usd="21.59")
    current = _position_response("0", asset_balance_usd="59.96")
    client = SequenceFakeClient([stale, current])

    positions = PositionAPI(client).get_positions(
        "0xwallet",
        reference_idle_usd=59.96,
        min_balance_usd=0.01,
    )

    assert positions == []
    assert len(client.calls) == 3


def test_positions_retry_empty_snapshot_against_reference_idle():
    empty = {"data": []}
    current = _position_response("10", asset_balance_usd="59.96")
    client = SequenceFakeClient([empty, current])

    positions = PositionAPI(client).get_positions(
        "0xwallet",
        reference_idle_usd=59.96,
        min_balance_usd=0.01,
    )

    assert len(positions) == 1
    assert positions[0]["balance_usd"] == 10.0
    assert len(client.calls) == 2


def test_positions_keep_consistent_snapshot_with_reference_idle():
    client = SequenceFakeClient([_position_response("10", asset_balance_usd="59.96")])

    positions = PositionAPI(client).get_positions(
        "0xwallet",
        reference_idle_usd=59.96,
        min_balance_usd=0.01,
    )

    assert len(positions) == 1
    assert positions[0]["balance_usd"] == 10.0


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


def test_opportunities_fetch_detailed_vaults_with_preference_filters():
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

    assert client.last_endpoint == "/v2/detailed-vaults"
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
        "maxTvl": 5_000_000,
        "maxApy": 0.20,
        "tags": ["stablecoin"],
        "curators": ["steakhouse"],
        "sortBy": "apy7day",
        "sortOrder": "desc",
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


def _vault_with_extras(**overrides):
    """Return a minimal vault dict with all new API fields, merged with overrides."""
    base = {
        "address": "0xbase",
        "name": "Base Vault",
        "network": {"name": "base"},
        "apy": {"total": 0.05},
        "tvl": {"usd": 2_000_000},
        "isTransactional": True,
        "depositStepsType": "instant",
        "redeemStepsType": "instant",
        "performanceFee": 0.10,
        "managementFee": 0.01,
        "withdrawalFee": 0.0,
        "depositFee": 0.0,
        "remainingCapacity": 500_000,
        "maxCapacity": 1_000_000,
        "rewardsSupported": True,
    }
    base.update(overrides)
    return base


def _response_with(*vaults):
    return {"userBalances": [{"asset": {"symbol": "USDC"}, "depositOptions": list(vaults)}]}


_BASE_CRITERIA = {"min_apy": 0.01, "min_tvl": 1_000_000, "only_transactional": True}


def test_opportunities_output_includes_new_fields():
    vault = _vault_with_extras()
    response = _response_with(vault)
    results = OpportunityAPI(FakeClient(response)).get_best_deposit_options("0xwallet", _BASE_CRITERIA)

    assert len(results) == 1
    r = results[0]
    assert r["deposit_steps_type"] == "instant"
    assert r["redeem_steps_type"] == "instant"
    assert r["performance_fee"] == 0.10
    assert r["management_fee"] == 0.01
    assert r["withdrawal_fee"] == 0.0
    assert r["deposit_fee"] == 0.0
    assert r["remaining_capacity"] == 500_000
    assert r["max_capacity"] == 1_000_000
    assert r["rewards_supported"] is True


def test_only_instant_deposit_excludes_non_instant():
    good = _vault_with_extras(address="0xgood", depositStepsType="instant")
    bad = _vault_with_extras(address="0xbad", depositStepsType="multi-step")
    results = OpportunityAPI(FakeClient(_response_with(good, bad))).get_best_deposit_options(
        "0xwallet", {**_BASE_CRITERIA, "only_instant_deposit": True},
    )
    assert [r["vault_address"] for r in results] == ["0xgood"]


def test_only_instant_redeem_excludes_non_instant():
    good = _vault_with_extras(address="0xgood", redeemStepsType="instant")
    bad = _vault_with_extras(address="0xbad", redeemStepsType="multi-step")
    results = OpportunityAPI(FakeClient(_response_with(good, bad))).get_best_deposit_options(
        "0xwallet", {**_BASE_CRITERIA, "only_instant_redeem": True},
    )
    assert [r["vault_address"] for r in results] == ["0xgood"]


def test_max_fee_filters_exclude_above_threshold():
    low = _vault_with_extras(address="0xlow", performanceFee=0.05, managementFee=0.005, withdrawalFee=0.0, depositFee=0.0)
    high = _vault_with_extras(address="0xhigh", performanceFee=0.30, managementFee=0.05, withdrawalFee=0.02, depositFee=0.01)
    criteria = {
        **_BASE_CRITERIA,
        "max_performance_fee": 0.20,
        "max_management_fee": 0.02,
        "max_withdrawal_fee": 0.01,
        "max_deposit_fee": 0.005,
    }
    results = OpportunityAPI(FakeClient(_response_with(low, high))).get_best_deposit_options("0xwallet", criteria)
    assert [r["vault_address"] for r in results] == ["0xlow"]


def test_fee_filter_passes_when_field_missing():
    """Vaults missing a fee field are NOT excluded (conservative)."""
    vault = _vault_with_extras(address="0xnofee")
    del vault["performanceFee"]
    criteria = {**_BASE_CRITERIA, "max_performance_fee": 0.10}
    results = OpportunityAPI(FakeClient(_response_with(vault))).get_best_deposit_options("0xwallet", criteria)
    assert len(results) == 1


def test_min_remaining_capacity_filters():
    big = _vault_with_extras(address="0xbig", remainingCapacity=200_000)
    small = _vault_with_extras(address="0xsmall", remainingCapacity=1_000)
    criteria = {**_BASE_CRITERIA, "min_remaining_capacity": 50_000}
    results = OpportunityAPI(FakeClient(_response_with(big, small))).get_best_deposit_options("0xwallet", criteria)
    assert [r["vault_address"] for r in results] == ["0xbig"]


def test_remaining_capacity_passes_when_field_missing():
    """Vaults missing remainingCapacity are NOT excluded (conservative)."""
    vault = _vault_with_extras(address="0xnocap")
    del vault["remainingCapacity"]
    criteria = {**_BASE_CRITERIA, "min_remaining_capacity": 50_000}
    results = OpportunityAPI(FakeClient(_response_with(vault))).get_best_deposit_options("0xwallet", criteria)
    assert len(results) == 1


def test_only_rewards_supported_excludes_unsupported():
    good = _vault_with_extras(address="0xgood", rewardsSupported=True)
    bad = _vault_with_extras(address="0xbad", rewardsSupported=False)
    missing = _vault_with_extras(address="0xmissing")
    del missing["rewardsSupported"]
    criteria = {**_BASE_CRITERIA, "only_rewards_supported": True}
    results = OpportunityAPI(FakeClient(_response_with(good, bad, missing))).get_best_deposit_options("0xwallet", criteria)
    assert [r["vault_address"] for r in results] == ["0xgood"]


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


def test_signable_transaction_strips_from_field():
    tx = {
        "from": "0xsender",
        "to": "0xvault",
        "data": "0x",
        "value": 0,
        "nonce": 1,
        "chainId": 8453,
        "gas": 21000,
        "gasPrice": 1,
    }

    assert TransactionExecutor._signable_transaction(tx) == {
        "to": "0xvault",
        "data": "0x",
        "value": 0,
        "nonce": 1,
        "chainId": 8453,
        "gas": 21000,
        "gasPrice": 1,
    }


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
            "minApy": "0.01",
            "minTvl": "1000000",
            "minVaultScore": "8",
            "onlyTransactional": "true",
            "allowCorrupted": "false",
        }
    ) == {
        "page": 0,
        "enabled": True,
        "disabled": False,
        "items": ["USDC", "WETH"],
        "minApy": 0.01,
        "minTvl": 1_000_000,
        "minVaultScore": 8,
        "onlyTransactional": "true",
        "allowCorrupted": "false",
    }


def test_v2_query_params_reject_invalid_boolean_strings():
    with pytest.raises(ValueError, match="onlyTransactional"):
        query_params({"onlyTransactional": "maybe"})


def test_x402_client_serializes_query_params_before_requests(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"ok": True}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return Response()

    monkeypatch.setattr("agent.api.client.requests.get", fake_get)

    client = X402Client(base_url="https://api.example")
    result = client.make_request(
        "/v2/detailed-vaults",
        params={"minApy": "0.01", "onlyTransactional": True, "allowCorrupted": False},
    )

    assert result == {"ok": True}
    assert captured["params"] == {
        "minApy": 0.01,
        "onlyTransactional": "true",
        "allowCorrupted": "false",
    }


def test_x402_paid_request_serializes_query_params_in_url(monkeypatch):
    captured = {}

    class Response:
        status_code = 402
        text = "payment required"

        def json(self):
            return {"error": "payment required"}

    class Completed:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    wallet = type("Wallet", (), {"name": "test-wallet", "passphrase": None})()

    def fake_get(url, params=None, headers=None, timeout=None):
        return Response()

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Completed()

    monkeypatch.setattr("agent.api.client.requests.get", fake_get)
    monkeypatch.setattr("agent.api.client.subprocess.run", fake_run)

    client = X402Client(wallet=wallet, base_url="https://api.example")
    client.ows_cli = "ows"
    result = client.make_request(
        "/v2/portfolio/best-deposit-options/0xabc",
        params={"minApy": "0.01", "onlyTransactional": True},
    )

    assert result == {"ok": True}
    paid_url = captured["command"][3]
    assert "minApy=0.01" in paid_url
    assert "onlyTransactional=true" in paid_url
    assert "onlyTransactional=True" not in paid_url
