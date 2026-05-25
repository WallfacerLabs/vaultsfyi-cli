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
