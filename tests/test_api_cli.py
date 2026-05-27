import json

import pytest
from typer.testing import CliRunner

from agent.api.v2 import query_params
from agent.cli.context import CliContext
from agent.cli.main import app


runner = CliRunner()
USER = "0x" + "1" * 40
ASSET = "0x" + "2" * 40
VAULT_ID = "vault-1"


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def request(self, endpoint, params=None, timeout=60):
        normalized = query_params(params or {})
        self.calls.append({"endpoint": endpoint, "params": normalized, "timeout": timeout})
        return {"endpoint": endpoint, "params": normalized}


def invoke_api(monkeypatch, args):
    fake = FakeApiClient()
    monkeypatch.setattr(CliContext, "api_client", lambda self: fake)
    result = runner.invoke(app, ["-o", "json", *args])
    assert result.exit_code == 0, result.stdout
    return fake.calls[-1], json.loads(result.stdout)


API_COMMAND_CASES = [
        (["api", "health"], "/v2/health", {}),
        (
            ["api", "vaults", "list", "--page", "1", "--per-page", "2", "--network", "base", "--asset-symbol", "USDC", "--only-transactional"],
            "/v2/vaults",
            {"page": 1, "perPage": 2, "network": "base", "assetSymbol": "USDC", "onlyTransactional": "true"},
        ),
        (["api", "assets", "list", "--network", "eip155:1"], "/v2/assets", {"network": "eip155:1"}),
        (["api", "tags"], "/v2/tags", {}),
        (["api", "networks"], "/v2/networks", {}),
        (["api", "curators"], "/v2/curators", {}),
        (["api", "protocols"], "/v2/protocols", {}),
        (
            ["api", "detailed-vaults", "list", "--allowed-asset", "USDC,WETH", "--allowed-network", "base", "--min-tvl", "1000", "--sort-by", "tvl"],
            "/v2/detailed-vaults",
            {"allowedAssets": ["USDC", "WETH"], "allowedNetworks": ["base"], "minTvl": 1000, "sortBy": "tvl"},
        ),
        (
            ["api", "detailed-vaults", "list", "--only-transactional", "--min-apy", "0.01"],
            "/v2/detailed-vaults",
            {"minApy": 0.01, "onlyTransactional": "true"},
        ),
        (["api", "detailed-vaults", "get", "eip155:1", VAULT_ID], "/v2/detailed-vaults/eip155%3A1/vault-1", {}),
        (["api", "detailed-vaults", "apy", "base", VAULT_ID], "/v2/detailed-vaults/base/vault-1/apy", {}),
        (["api", "detailed-vaults", "tvl", "base", VAULT_ID], "/v2/detailed-vaults/base/vault-1/tvl", {}),
        (
            ["api", "historical", "vault", "base", VAULT_ID, "--apy-interval", "7day", "--granularity", "1day", "--from-timestamp", "10"],
            "/v2/historical/base/vault-1",
            {"apyInterval": "7day", "granularity": "1day", "fromTimestamp": 10},
        ),
        (["api", "historical", "apy", "base", VAULT_ID], "/v2/historical/base/vault-1/apy", {}),
        (["api", "historical", "tvl", "base", VAULT_ID], "/v2/historical/base/vault-1/tvl", {}),
        (["api", "historical", "share-price", "base", VAULT_ID], "/v2/historical/base/vault-1/sharePrice", {}),
        (["api", "historical", "asset-prices", "base", ASSET, "--to-timestamp", "20"], f"/v2/historical/asset-prices/base/{ASSET}", {"toTimestamp": 20}),
        (["api", "portfolio", "best-vault", USER, "--allowed-asset", "USDC", "--min-apy", "0.02"], f"/v2/portfolio/best-vault/{USER}", {"allowedAssets": ["USDC"], "minApy": 0.02}),
        (["api", "portfolio", "positions", USER, "--sort-by", "balanceUsd", "--apy-interval", "30day"], f"/v2/portfolio/positions/{USER}", {"sortBy": "balanceUsd", "apyInterval": "30day"}),
        (["api", "portfolio", "position", USER, "base", VAULT_ID, "--apy-interval", "1day"], f"/v2/portfolio/positions/{USER}/base/vault-1", {"apyInterval": "1day"}),
        (
            ["api", "portfolio", "best-deposit-options", USER, "--always-return-asset", "USDC", "--max-vaults-per-asset", "5"],
            f"/v2/portfolio/best-deposit-options/{USER}",
            {"alwaysReturnAssets": ["USDC"], "maxVaultsPerAsset": 5},
        ),
        (["api", "portfolio", "idle-assets", USER, "--sort-by", "balanceUsd", "--sort-direction", "desc"], f"/v2/portfolio/idle-assets/{USER}", {"sortBy": "balanceUsd", "sortDirection": "desc"}),
        (["api", "portfolio", "total-returns", USER, "base", VAULT_ID], f"/v2/portfolio/total-returns/{USER}/base/vault-1", {}),
        (["api", "portfolio", "events", USER, "base", VAULT_ID], f"/v2/portfolio/events/{USER}/base/vault-1", {}),
        (["api", "transactions", "context", USER, "base", VAULT_ID], f"/v2/transactions/context/{USER}/base/vault-1", {}),
        (["api", "transactions", "suffix", USER, VAULT_ID], f"/v2/transactions/suffix/{USER}/vault-1", {}),
        (
            ["api", "transactions", "payload", "deposit", USER, "base", VAULT_ID, "--asset-address", ASSET, "--amount", "100", "--simulate"],
            f"/v2/transactions/deposit/{USER}/base/vault-1",
            {"assetAddress": ASSET, "amount": 100, "simulate": "true"},
        ),
        (["api", "transactions", "rewards", "context", USER], f"/v2/transactions/rewards/context/{USER}", {}),
        (
            ["api", "transactions", "rewards", "claim", USER, "--claim-id", "a,b"],
            f"/v2/transactions/rewards/claim/{USER}",
            {"claimIds": ["a", "b"]},
        ),
        (["api", "benchmarks", "get", "base", "--code", "usd"], "/v2/benchmarks/base", {"code": "usd"}),
        (["api", "benchmarks", "history", "base", "--code", "eth", "--page", "1"], "/v2/historical-benchmarks/base", {"code": "eth", "page": 1}),
        (["api", "nrt", "vault", "base", VAULT_ID], "/v2/nrt/vault/base/vault-1", {}),
        (["api", "nrt", "share-price", "base", VAULT_ID], "/v2/nrt/vault/base/vault-1/sharePrice", {}),
        (["api", "nrt", "total-supply", "base", VAULT_ID], "/v2/nrt/vault/base/vault-1/totalSupply", {}),
        (["api", "nrt", "total-assets", "base", VAULT_ID], "/v2/nrt/vault/base/vault-1/totalAssets", {}),
        (["api", "nrt", "underlying-asset-price", "base", VAULT_ID], "/v2/nrt/vault/base/vault-1/underlyingAssetPrice", {}),
        (["api", "request", "/v2/custom", "-q", "foo=bar", "-q", "foo=baz"], "/v2/custom", {"foo": ["bar", "baz"]}),
]


@pytest.mark.parametrize(("args", "endpoint", "params"), API_COMMAND_CASES)
def test_api_commands_map_to_expected_endpoint_and_params(monkeypatch, args, endpoint, params):
    call, payload = invoke_api(monkeypatch, args)
    assert call["endpoint"] == endpoint
    assert call["params"] == params
    assert payload == {"endpoint": endpoint, "params": params}


def test_claim_rewards_requires_claim_id(monkeypatch):
    fake = FakeApiClient()
    monkeypatch.setattr(CliContext, "api_client", lambda self: fake)
    result = runner.invoke(app, ["-o", "json", "api", "transactions", "rewards", "claim", USER])
    assert result.exit_code != 0
    assert "--claim-id is required" in result.stdout
