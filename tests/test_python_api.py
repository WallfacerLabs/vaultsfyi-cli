import os
import tempfile

import pytest
from eth_account import Account
from ows import import_wallet_private_key

from agent import Agent
from agent.core.executor import TransactionExecutor
from agent.core.wallet import Wallet


def test_ows_signing_matches_eth_account(monkeypatch):
    private_key = "0x" + "11" * 32
    vault = tempfile.mkdtemp(prefix="vaultsfyi-test-ows-")
    import_wallet_private_key("agent-treasury", private_key, passphrase="", vault_path_opt=vault)

    monkeypatch.setenv("OWS_WALLET", "agent-treasury")
    monkeypatch.setenv("OWS_CHAIN", "base")
    monkeypatch.setenv("OWS_VAULT_PATH", vault)
    monkeypatch.setenv("OWS_PASSPHRASE", "")

    wallet = Wallet()
    assert wallet.address == Account.from_key(private_key).address

    executor = TransactionExecutor.__new__(TransactionExecutor)
    executor.wallet = wallet
    tx = {
        "nonce": 0,
        "gasPrice": 1_000_000_000,
        "gas": 21_000,
        "to": "0x" + "22" * 20,
        "value": 123,
        "data": b"",
        "chainId": 8453,
    }
    assert executor._sign_with_ows(tx).hex() == Account.sign_transaction(tx, private_key).raw_transaction.hex()


def test_agent_accepts_config_dict(monkeypatch):
    class FakeWallet:
        address = "0xabc"

    class FakeExecutor:
        def __init__(self, wallet):
            self.wallet = wallet

    monkeypatch.setattr("agent.agent.Wallet", lambda: FakeWallet())
    monkeypatch.setattr("agent.agent.TransactionExecutor", FakeExecutor)

    cfg = {
        "vaults_api_url": "https://api.vaults.fyi",
        "network": "base",
        "asset": "USDC",
        "asset_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "investment": {"min_deposit_usd": 0.1},
        "criteria": {"min_apy": 0.01, "min_tvl": 1_000_000, "only_transactional": True},
        "display": {"decimals": 2, "position_retry_attempts": 1, "position_retry_delay": 0},
        "vault_whitelist": [],
    }
    agent = Agent(config=cfg)
    assert agent.network == "base"
    assert agent.wallet.address == "0xabc"


def test_agent_rejects_out_of_range_percentages():
    agent = Agent.__new__(Agent)

    with pytest.raises(ValueError, match="Deploy percentage"):
        agent.prepare_deploy(0)
    with pytest.raises(ValueError, match="Deploy percentage"):
        agent.prepare_deploy(101)
    with pytest.raises(ValueError, match="Redeem percentage"):
        agent.prepare_redeem("pos", -1)
    with pytest.raises(ValueError, match="Redeem percentage"):
        agent.prepare_redeem("pos", 101)


def test_prepare_redeem_rejects_ambiguous_nicknames():
    class FakeExecutor:
        def validate_gas_balance(self):
            return True, ""

    agent = Agent.__new__(Agent)
    agent.executor = FakeExecutor()
    agent.get_positions = lambda: [
        {"nickname": "SameVault", "vault_name": "Same Vault A", "vault_address": "0xa", "balance_usd": 1},
        {"nickname": "SameVault", "vault_name": "Same Vault B", "vault_address": "0xb", "balance_usd": 1},
    ]

    with pytest.raises(ValueError, match="ambiguous"):
        agent.prepare_redeem("SameVault", 50)


def test_prepare_redeem_leaves_dust_on_full_redemption():
    class FakeExecutor:
        def validate_gas_balance(self):
            return True, ""

    class FakeTransactionAPI:
        def __init__(self):
            self.calls = []

        def generate_redeem_tx(
            self,
            user_address,
            vault_address,
            lp_token_amount,
            lp_decimals,
            asset_address,
            network,
            is_full_redemption=False,
        ):
            self.calls.append(
                {
                    "lp_token_amount": lp_token_amount,
                    "is_full_redemption": is_full_redemption,
                }
            )
            return [{"to": vault_address, "data": "0x", "value": "0"}]

    tx_api = FakeTransactionAPI()
    agent = Agent.__new__(Agent)
    agent.executor = FakeExecutor()
    agent.transaction_api = tx_api
    agent.wallet = type("Wallet", (), {"address": "0xwallet"})()
    agent.asset_address = "0xasset"
    agent.network = "base"
    agent.redeem_dust_usd = 0.01
    agent.get_positions = lambda: [
        {
            "nickname": "Vault",
            "vault_name": "Vault",
            "vault_address": "0xvault",
            "balance_usd": 100.0,
            "balance_lp_tokens": 100.0,
            "lp_decimals": 18,
        }
    ]

    plan = agent.prepare_redeem("Vault", 100)

    assert plan["amount_usd"] == pytest.approx(99.99)
    assert plan["dust_adjusted"] is True
    assert plan["lp_tokens"] == pytest.approx(99.99)
    assert tx_api.calls[0]["lp_token_amount"] == pytest.approx(99.99)
    assert tx_api.calls[0]["is_full_redemption"] is False


def test_prepare_redeem_rejects_dust_position():
    class FakeExecutor:
        def validate_gas_balance(self):
            return True, ""

    agent = Agent.__new__(Agent)
    agent.executor = FakeExecutor()
    agent.redeem_dust_usd = 0.01
    agent.get_positions = lambda: [
        {
            "nickname": "Dust",
            "vault_name": "Dust",
            "vault_address": "0xdust",
            "balance_usd": 0.009,
            "balance_lp_tokens": 0.009,
            "lp_decimals": 18,
        }
    ]

    with pytest.raises(ValueError, match="below redeem dust threshold"):
        agent.prepare_redeem("Dust", 100)


def test_agent_get_positions_fetches_fresh_idle_reference_each_call():
    class FakePositionAPI:
        def __init__(self):
            self.idle_calls = 0
            self.position_calls = 0

        def get_idle_assets(self, wallet_address):
            self.idle_calls += 1
            return {"usdc_balance": 100 + self.idle_calls, "balance_tokens": 100}

        def get_positions(self, wallet_address, **kwargs):
            self.position_calls += 1
            return [{"reference_idle_usd": kwargs["reference_idle_usd"]}]

    position_api = FakePositionAPI()
    agent = Agent.__new__(Agent)
    agent.position_api = position_api
    agent.wallet = type("Wallet", (), {"address": "0xwallet"})()
    agent.redeem_dust_usd = 0.01

    first = agent.get_positions()
    second = agent.get_positions()

    assert position_api.idle_calls == 2
    assert position_api.position_calls == 2
    assert first[0]["reference_idle_usd"] == 101.0
    assert second[0]["reference_idle_usd"] == 102.0
