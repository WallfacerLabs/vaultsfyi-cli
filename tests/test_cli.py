import json

from typer.testing import CliRunner

from agent.cli.main import app
from agent.cli.context import CliContext

runner = CliRunner()


class FakeAgent:
    display_decimals = 2
    wallet = type("Wallet", (), {"address": "0xabc"})()

    def get_state(self):
        return {
            "wallet": "0xabc",
            "network": "base",
            "asset": "USDC",
            "gas": {"balance_eth": 0.01, "sufficient": True, "min_required_eth": 0.001},
            "idle_assets": {"usdc_balance": 100.0, "balance_tokens": 100.0},
            "positions_count": 1,
        }

    def get_idle_assets(self):
        return {"usdc_balance": 100.0, "balance_tokens": 100.0}

    def get_positions(self):
        return [
            {
                "nickname": "YearnUSDCV",
                "vault_name": "Yearn USDC Vault",
                "asset": "USDC",
                "apy": 0.05,
                "balance_usd": 10.0,
                "balance_lp_tokens": 10.0,
                "lp_decimals": 6,
                "vault_address": "0xvault",
                "network": "base",
            }
        ]

    def get_opportunities(self):
        return [
            {
                "vault_name": "Yearn USDC Vault",
                "vault_address": "0xvault",
                "apy": 0.05,
                "tvl": 1_000_000,
                "network": "base",
                "asset": "USDC",
            }
        ]

    def prepare_deploy(self, percentage):
        return {
            "action": "deploy",
            "status": "planned",
            "percentage": percentage,
            "amount_usd": 10.0,
            "vault": self.get_opportunities()[0],
            "transactions": [{"to": "0xvault", "data": "0x", "value": "0"}],
            "transaction_count": 1,
        }

    def execute_deploy_plan(self, plan):
        return {**plan, "status": "submitted", "tx_hashes": ["0x123"]}

    def prepare_redeem(self, position, percentage=100.0):
        return {
            "action": "redeem",
            "status": "planned",
            "percentage": percentage,
            "amount_usd": 5.0,
            "position": self.get_positions()[0],
            "transactions": [{"to": "0xvault", "data": "0x", "value": "0"}],
            "transaction_count": 1,
        }

    def execute_redeem_plan(self, plan):
        return {**plan, "status": "submitted", "tx_hashes": ["0x456"]}


def fake_agent(self):
    return FakeAgent()


def test_help_lists_core_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "deploy" in result.stdout
    assert "wallet" in result.stdout
    assert "agent" in result.stdout


def test_status_json(monkeypatch):
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    result = runner.invoke(app, ["-o", "json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["wallet"] == "0xabc"
    assert data["positions_count"] == 1


def test_positions_table(monkeypatch):
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    result = runner.invoke(app, ["positions"])
    assert result.exit_code == 0
    assert "YearnUSDCV" in result.stdout
    assert "Yearn USDC Vault" in result.stdout


def test_deploy_json_requires_yes(monkeypatch):
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    result = runner.invoke(app, ["-o", "json", "deploy", "--percent", "10"])
    assert result.exit_code != 0
    data = json.loads(result.stdout)
    assert "--yes" in data["error"]


def test_deploy_json_with_yes(monkeypatch):
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    result = runner.invoke(app, ["-o", "json", "deploy", "--percent", "10", "--yes"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "submitted"
    assert data["tx_hashes"] == ["0x123"]


def test_redeem_dry_run_json(monkeypatch):
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    result = runner.invoke(app, ["-o", "json", "redeem", "--position", "YearnUSDCV", "--percent", "50", "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "dry_run"
    assert data["position"]["nickname"] == "YearnUSDCV"


def test_agent_init_and_list(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = runner.invoke(app, ["-o", "json", "agent", "init", "conservative", "--wallet", "ows-conservative"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["name"] == "conservative"
    assert data["wallet"] == "ows-conservative"

    result = runner.invoke(app, ["-o", "json", "agent", "list"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert rows[0]["name"] == "conservative"
    assert rows[0]["wallet"] == "ows-conservative"


def test_global_agent_profile_selects_wallet(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    runner.invoke(app, ["agent", "init", "high-yield", "--wallet", "ows-high-yield"])
    result = runner.invoke(app, ["--agent", "high-yield", "-o", "json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agent"]["name"] == "high-yield"
    assert data["wallet"]["name"] == "ows-high-yield"


def test_config_show_hides_advanced_sections_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = runner.invoke(app, ["-o", "json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "wallet" in data
    assert "strategy" in data
    assert "agent" not in data
    assert "risk" not in data
    assert "execution" not in data

    result = runner.invoke(app, ["-o", "json", "config", "show", "--all"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "agent" in data
    assert "risk" in data
    assert "execution" in data


def test_agent_run_dry_run_json(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    runner.invoke(app, ["agent", "init", "conservative", "--wallet", "ows-conservative"])
    result = runner.invoke(app, ["-o", "json", "agent", "run", "conservative", "--dry-run"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agent"] == "conservative"
    assert data["wallet"] == "ows-conservative"
    assert data["plan"]["status"] == "dry_run"


def test_preference_init_set_and_list(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = runner.invoke(app, ["-o", "json", "preference", "init", "blue-chip"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["name"] == "blue-chip"

    result = runner.invoke(app, ["preference", "set", "blue-chip", "min_tvl", "10000000"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["-o", "json", "preference", "list"])
    rows = json.loads(result.stdout)
    assert rows[0]["name"] == "blue-chip"
    assert rows[0]["min_tvl"] == 10_000_000


def test_decision_packet_and_validate(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    runner.invoke(app, ["preference", "init", "blue-chip"])

    result = runner.invoke(app, ["-o", "json", "decision-packet", "--preference", "blue-chip"])
    assert result.exit_code == 0
    packet = json.loads(result.stdout)
    assert packet["schema_version"] == "vaultsfyi.decision-packet.v1"
    assert packet["candidate_actions"][0]["id"] == "hold"

    packet_path = tmp_path / "packet.json"
    decision_path = tmp_path / "decision.json"
    packet_path.write_text(json.dumps(packet))
    decision_path.write_text(json.dumps({"schema_version": "vaultsfyi.decision.v1", "candidate_id": "hold", "action": "hold"}))

    result = runner.invoke(app, ["-o", "json", "validate-decision", str(decision_path), "--packet", str(packet_path)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["valid"] is True

    decision_path.write_text(json.dumps({"schema_version": "vaultsfyi.decision.v1", "candidate_id": "made-up", "action": "deploy_idle"}))
    result = runner.invoke(app, ["-o", "json", "validate-decision", str(decision_path), "--packet", str(packet_path)])
    assert result.exit_code != 0
    assert json.loads(result.stdout)["valid"] is False
