import json
import os

from typer.testing import CliRunner

from agent.cli import config as config_mod
from agent.cli.main import app
from agent.cli.context import CliContext
from agent.decision import apply_preference, build_candidate_actions, plan_decision, preference_bucket_state, validate_decision

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

    def prepare_redeem_by_vault(self, vault_address, amount_usd=None, percentage=None):
        return {
            "action": "redeem",
            "position": self.get_positions()[0],
            "amount_usd": amount_usd,
            "transactions": [{"to": vault_address, "data": "0xredeem", "value": "0"}],
        }

    def prepare_deploy_to_vault(self, vault_address, amount_usd, **kwargs):
        return {
            "action": "deploy_idle",
            "vault": {"vault_address": vault_address, "vault_name": "Target Vault"},
            "amount_usd": amount_usd,
            "available_usd": kwargs.get("available_usd"),
            "transactions": [{"to": vault_address, "data": "0xdeploy", "value": "0"}],
        }


def fake_agent(self):
    return FakeAgent()


def test_exported_env_restores_and_clears_managed_values(monkeypatch):
    monkeypatch.setenv("OWS_VAULT_PATH", "/external-vault")
    cfg = {
        "wallet": {"name": "agent-one", "chain": "base", "vault_path": None, "ows_cli_path": None},
        "network": {"rpc_url": "https://rpc.example"},
        "vaults": {"api_key": None, "api_url": "https://api.example"},
    }

    with config_mod.exported_env(cfg):
        assert os.environ["OWS_WALLET"] == "agent-one"
        assert "OWS_VAULT_PATH" not in os.environ

    assert os.environ["OWS_VAULT_PATH"] == "/external-vault"


def test_load_config_reads_cwd_dotenv_without_overriding_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("VAULTS_API_KEY=dotenv-key\nVAULTS_API_URL=https://dotenv.example\n")

    monkeypatch.delenv("VAULTS_API_KEY", raising=False)
    monkeypatch.setenv("VAULTS_API_URL", "https://env.example")
    cfg = config_mod.load_config()

    assert cfg["vaults"]["api_key"] == "dotenv-key"
    assert cfg["vaults"]["api_url"] == "https://env.example"


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


def test_deploy_json_with_yes(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
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
    result = runner.invoke(app, ["preference", "set", "blue-chip", "bucket_max_pct", "10"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["preference", "set", "blue-chip", "bucket_tolerance_pct", "5"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["-o", "json", "preference", "list"])
    rows = json.loads(result.stdout)
    assert rows[0]["name"] == "blue-chip"
    assert rows[0]["min_tvl"] == 10_000_000
    assert rows[0]["bucket_max_pct"] == 10
    assert rows[0]["bucket_tolerance_pct"] == 5


def test_preference_overlay_supports_detailed_vault_filters():
    cfg = config_mod.DEFAULT_CONFIG | {
        "preferences": {
            "detailed": {
                "allowed_assets": ["USDC", "WETH"],
                "disallowed_assets": ["DAI"],
                "allowed_networks": ["base"],
                "disallowed_networks": ["polygon"],
                "allowed_protocols": ["morpho"],
                "disallowed_protocols": ["aave"],
                "blocked_protocols": [],
                "min_tvl": 5_000_000,
                "max_tvl": 50_000_000,
                "min_apy": 0.02,
                "max_apy": 0.15,
                "min_vault_score": 8,
                "only_transactional": True,
                "only_app_featured": True,
                "allow_corrupted": False,
                "allow_vaults_with_warnings": False,
                "tags": ["stablecoin"],
                "curators": ["steakhouse"],
                "allowed_curators": [],
                "sort_by": "apy7day",
                "sort_order": "desc",
                "page": 1,
                "per_page": 25,
                "bucket_max_pct": 10,
                "bucket_tolerance_pct": 5,
            }
        }
    }

    resolved = apply_preference(cfg, "detailed")
    criteria = config_mod.agent_config(resolved)["criteria"]

    assert "bucket_max_pct" not in resolved["strategy"]
    assert resolved["active_preference"]["filters"]["bucket_max_pct"] == 10
    assert criteria["allowed_assets"] == ["USDC", "WETH"]
    assert criteria["disallowed_assets"] == ["DAI"]
    assert criteria["allowed_networks"] == ["base"]
    assert criteria["disallowed_networks"] == ["polygon"]
    assert criteria["allowed_protocols"] == ["morpho"]
    assert criteria["disallowed_protocols"] == ["aave"]
    assert criteria["min_tvl"] == 5_000_000
    assert criteria["max_tvl"] == 50_000_000
    assert criteria["min_apy"] == 0.02
    assert criteria["max_apy"] == 0.15
    assert criteria["min_vault_score"] == 8
    assert criteria["only_app_featured"] is True
    assert criteria["allow_corrupted"] is False
    assert criteria["allow_vaults_with_warnings"] is False
    assert criteria["tags"] == ["stablecoin"]
    assert criteria["curators"] == ["steakhouse"]
    assert criteria["sort_by"] == "apy7day"
    assert criteria["sort_order"] == "desc"
    assert criteria["page"] == 1
    assert criteria["per_page"] == 25


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


def test_decision_packet_includes_preference_bucket(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    runner.invoke(app, ["preference", "init", "degen"])
    runner.invoke(app, ["preference", "set", "degen", "bucket_max_pct", "10"])
    runner.invoke(app, ["preference", "set", "degen", "bucket_tolerance_pct", "5"])

    result = runner.invoke(app, ["-o", "json", "decision-packet", "--preference", "degen"])

    assert result.exit_code == 0
    packet = json.loads(result.stdout)
    bucket = packet["constraints"]["preference_bucket"]
    assert bucket["preference"] == "degen"
    assert bucket["max_pct"] == 10.0
    assert bucket["tolerance_pct"] == 5.0
    assert bucket["current_usd"] == 10.0
    assert bucket["remaining_deploy_usd"] == 1.0
    assert bucket["status"] == "under_limit"


def test_validate_decision_rejects_action_mismatch():
    packet = {
        "schema_version": "vaultsfyi.decision-packet.v1",
        "eligible_vaults": [],
        "current_positions": [],
        "candidate_actions": [{"id": "hold", "type": "hold", "amount_usd": 0}],
        "constraints": {"decision": {"min_net_gain_usd": 0}},
    }
    decision = {"schema_version": "vaultsfyi.decision.v1", "candidate_id": "hold", "action": "deploy_idle"}
    result = validate_decision(decision, packet)
    assert result["valid"] is False
    assert "decision action does not match candidate type" in result["violations"]


def test_validate_decision_rejects_preference_bucket_capacity_violation():
    packet = {
        "schema_version": "vaultsfyi.decision-packet.v1",
        "eligible_vaults": [{"vault_address": "0xDEGEN"}],
        "current_positions": [],
        "candidate_actions": [
            {
                "id": "deploy_idle:0xDEGEN:20.000000",
                "type": "deploy_idle",
                "target_vault_address": "0xDEGEN",
                "amount_usd": 20.0,
                "annual_yield_gain_usd": 10.0,
                "breakeven_days": 1,
                "estimated_cost": {"tx_cost_usd": 0.0},
            }
        ],
        "constraints": {
            "decision": {"min_net_gain_usd": 0, "max_breakeven_days": 30},
            "preference_bucket": {"remaining_deploy_usd": 10.0, "matched_vault_addresses": ["0xdegen"]},
        },
    }
    decision = {
        "schema_version": "vaultsfyi.decision.v1",
        "candidate_id": "deploy_idle:0xDEGEN:20.000000",
        "action": "deploy_idle",
    }

    result = validate_decision(decision, packet)

    assert result["valid"] is False
    assert "candidate exceeds preference bucket remaining deploy capacity" in result["violations"]


def test_deploy_preference_bucket_caps_requested_percent(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(CliContext, "agent", fake_agent)
    runner.invoke(app, ["preference", "init", "degen"])
    runner.invoke(app, ["preference", "set", "degen", "bucket_max_pct", "10"])
    runner.invoke(app, ["preference", "set", "degen", "bucket_tolerance_pct", "5"])

    result = runner.invoke(app, ["-o", "json", "deploy", "--percent", "10", "--preference", "degen", "--dry-run"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["percentage"] == 1.0


def test_candidate_actions_do_not_deploy_idle_into_existing_positions():
    opportunities = [
        {"vault_address": "0xEXISTING", "vault_name": "Existing", "apy": 0.08},
        {"vault_address": "0xNEW", "vault_name": "New", "apy": 0.07},
    ]
    positions = [{"vault_address": "0xexisting", "balance_usd": 100.0, "apy": 0.03}]
    idle = {"usdc_balance": 100.0}
    cfg = {
        "agent": {"max_position_pct": 10},
        "strategy": {"min_deposit_usd": 0.1},
        "decision": {"min_apy_improvement": 0.01},
    }

    candidates = build_candidate_actions(FakeAgent(), cfg, opportunities, positions, idle)
    deploy_candidates = [c for c in candidates if c["type"] == "deploy_idle"]
    assert [c["target_vault_address"] for c in deploy_candidates] == ["0xNEW"]
    assert deploy_candidates[0]["amount_usd"] == 20.0


def test_preference_bucket_caps_candidates_that_increase_bucket_exposure():
    opportunities = [
        {"vault_address": "0xDEGEN_OLD", "vault_name": "Old Degen", "apy": 0.03},
        {"vault_address": "0xDEGEN_NEW", "vault_name": "New Degen", "apy": 0.10},
    ]
    positions = [
        {"vault_address": "0xDEGEN_OLD", "vault_name": "Old Degen", "nickname": "old", "balance_usd": 8.0, "apy": 0.02},
        {"vault_address": "0xSAFE", "vault_name": "Safe", "nickname": "safe", "balance_usd": 42.0, "apy": 0.01},
    ]
    idle = {"usdc_balance": 50.0}
    cfg = {
        "active_preference": {"name": "degen", "filters": {"bucket_max_pct": 10, "bucket_tolerance_pct": 5}},
        "agent": {},
        "risk": {},
        "strategy": {"min_deposit_usd": 0.1},
        "decision": {"min_apy_improvement": 0.01},
    }

    state = preference_bucket_state(cfg, opportunities, positions, idle)
    candidates = build_candidate_actions(FakeAgent(), cfg, opportunities, positions, idle)

    assert state["current_pct"] == 8.0
    assert state["remaining_deploy_usd"] == 2.0
    deploy_candidates = [c for c in candidates if c["type"] == "deploy_idle"]
    assert deploy_candidates[0]["amount_usd"] == 2.0
    incoming_rebalances = [c for c in candidates if c.get("source_vault_address") == "0xSAFE"]
    assert incoming_rebalances
    assert {c["type"] for c in incoming_rebalances} == {"partial_rebalance"}
    assert {c["amount_usd"] for c in incoming_rebalances} == {2.0}


def test_preference_bucket_reports_tolerance_band_status():
    cfg = {
        "active_preference": {"name": "degen", "filters": {"bucket_max_pct": 10, "bucket_tolerance_pct": 5}},
    }
    opportunities = [{"vault_address": "0xDEGEN"}]

    state = preference_bucket_state(cfg, opportunities, [{"vault_address": "0xDEGEN", "balance_usd": 12.0}], {"usdc_balance": 88.0})
    assert state["status"] == "within_tolerance"
    assert state["remaining_deploy_usd"] == 0.0

    state = preference_bucket_state(cfg, opportunities, [{"vault_address": "0xDEGEN", "balance_usd": 16.0}], {"usdc_balance": 84.0})
    assert state["status"] == "over_tolerance"


def test_plan_decision_rebalance_uses_projected_available_idle():
    packet = {
        "schema_version": "vaultsfyi.decision-packet.v1",
        "idle_assets": {"usdc_balance": 1.0},
        "eligible_vaults": [{"vault_address": "0xtarget"}],
        "current_positions": [{"vault_address": "0xsource"}],
        "candidate_actions": [
            {
                "id": "partial_rebalance:0xsource:0xtarget:5.000000",
                "type": "partial_rebalance",
                "source_vault_address": "0xsource",
                "target_vault_address": "0xtarget",
                "amount_usd": 5.0,
                "annual_yield_gain_usd": 5.0,
                "breakeven_days": 1,
                "estimated_cost": {"tx_cost_usd": 0.0},
            }
        ],
        "constraints": {"decision": {"min_net_gain_usd": 0, "max_breakeven_days": 30}},
    }
    decision = {
        "schema_version": "vaultsfyi.decision.v1",
        "candidate_id": "partial_rebalance:0xsource:0xtarget:5.000000",
        "action": "partial_rebalance",
    }

    result = plan_decision(FakeAgent(), decision, packet)
    assert result["valid"] is True
    assert result["deploy_plan"]["available_usd"] == 6.0
