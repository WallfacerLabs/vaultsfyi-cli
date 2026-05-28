import pytest

from agent.decision import build_candidate_actions, portfolio_summary, preference_bucket_state


class FakeAgent:
    pass


def test_preference_bucket_caps_use_total_portfolio_not_idle_only():
    cfg = {
        "strategy": {"min_deposit_usd": 0.10},
        "active_preference": {"name": "bucket", "filters": {"bucket_max_pct": 10}},
    }
    opportunities = [{"vault_address": "0xBUCKET", "vault_name": "Bucket", "apy": 0.05}]
    positions = [{"vault_address": "0xOTHER", "balance_usd": 40.0, "apy": 0.02}]
    idle = {"usdc_balance": 60.0}

    state = preference_bucket_state(cfg, opportunities, positions, idle)
    candidates = build_candidate_actions(FakeAgent(), cfg, opportunities, positions, idle)

    assert state["portfolio_usd"] == 100.0
    assert state["max_usd"] == 10.0
    assert state["remaining_deploy_usd"] == 10.0
    deploy = next(candidate for candidate in candidates if candidate["type"] == "deploy_idle")
    assert deploy["amount_usd"] == pytest.approx(10.0)


def test_portfolio_summary_uses_idle_plus_positions():
    summary = portfolio_summary(
        {"usdc_balance": 60.0},
        [
            {"balance_usd": 35.0},
            {"balance_usd": 5.0},
        ],
    )

    assert summary == {"idle_usd": 60.0, "positions_usd": 40.0, "total_usd": 100.0}
