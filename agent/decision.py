"""Deterministic decision packet, validation, and planning helpers.

OpenClaw or another external allocator can reason over a packet and return a
strict decision object. This module treats that decision as untrusted input.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

PACKET_SCHEMA = "vaultsfyi.decision-packet.v1"
DECISION_SCHEMA = "vaultsfyi.decision.v1"

DEFAULT_DECISION_CONFIG: dict[str, Any] = {
    "min_net_gain_usd": 1.0,
    "max_breakeven_days": 30,
    "min_apy_improvement": 0.01,
    "max_rebalance_pct": 50,
    "allow_partial_rebalance": True,
    "prefer_hold_if_uncertain": True,
    "eth_usd_price": 3000.0,
    "deposit_gas_units": 350_000,
    "redeem_gas_units": 500_000,
}

PREFERENCE_KEYS = {
    "network",
    "asset",
    "asset_address",
    "min_deposit_usd",
    "min_apy",
    "max_apy",
    "min_tvl",
    "apy_interval",
    "only_transactional",
    "vault_whitelist",
    "allowed_protocols",
    "blocked_protocols",
    "allowed_curators",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def decision_config(cfg: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(DEFAULT_DECISION_CONFIG)
    merged.update(cfg.get("decision", {}))
    return merged


def apply_preference(cfg: dict[str, Any], preference_name: str | None) -> dict[str, Any]:
    """Return a copy of cfg with a named preference overlaid onto strategy."""
    resolved = deepcopy(cfg)
    if not preference_name:
        return resolved
    preferences = resolved.get("preferences", {})
    if preference_name not in preferences:
        raise ValueError(f"preference '{preference_name}' does not exist")
    preference = preferences[preference_name]
    for key, value in preference.items():
        if key in PREFERENCE_KEYS:
            resolved.setdefault("strategy", {})[key] = value
    resolved.setdefault("active_preference", {})["name"] = preference_name
    resolved["active_preference"]["filters"] = preference
    return resolved


def _finite_days(tx_cost_usd: float, annual_gain_usd: float) -> float | None:
    if annual_gain_usd <= 0:
        return None
    return tx_cost_usd / (annual_gain_usd / 365)


def _cost(action_type: str, cfg: dict[str, Any], gas_price_wei: int | None = None) -> dict[str, Any]:
    dc = decision_config(cfg)
    gas_price_wei = gas_price_wei or 100_000_000  # conservative-ish default when RPC gas price is unavailable
    gas_units = 0
    if action_type == "deploy_idle":
        gas_units = int(dc["deposit_gas_units"])
    elif action_type in {"rebalance", "partial_rebalance"}:
        gas_units = int(dc["redeem_gas_units"]) + int(dc["deposit_gas_units"])
    tx_cost_eth = (gas_units * gas_price_wei) / 1e18
    tx_cost_usd = tx_cost_eth * float(dc["eth_usd_price"])
    return {
        "gas_units": gas_units,
        "gas_price_wei": gas_price_wei,
        "tx_cost_eth": tx_cost_eth,
        "tx_cost_usd": tx_cost_usd,
        "eth_usd_price": float(dc["eth_usd_price"]),
    }


def build_candidate_actions(agent, cfg: dict[str, Any], opportunities: list[dict], positions: list[dict], idle_assets: dict) -> list[dict]:
    """Build legal action candidates from already-filtered opportunities."""
    dc = decision_config(cfg)
    candidates: list[dict[str, Any]] = [{
        "id": "hold",
        "type": "hold",
        "description": "Do nothing",
        "amount_usd": 0,
        "annual_yield_gain_usd": 0,
        "breakeven_days": None,
        "estimated_cost": _cost("hold", cfg),
    }]

    idle_usd = float(idle_assets.get("usdc_balance", 0))
    min_deposit = float(cfg.get("strategy", {}).get("min_deposit_usd", 0.10))
    max_agent_deploy = cfg.get("agent", {}).get("max_deploy_usd")
    max_single = cfg.get("risk", {}).get("max_single_vault_usd")
    caps = [float(v) for v in [max_agent_deploy, max_single] if v is not None]
    deploy_amount = idle_usd if not caps else min(idle_usd, min(caps))

    for vault in opportunities[:10]:
        if deploy_amount >= min_deposit:
            c = _cost("deploy_idle", cfg)
            annual_gain = deploy_amount * float(vault.get("apy", 0))
            breakeven = _finite_days(c["tx_cost_usd"], annual_gain)
            candidates.append({
                "id": f"deploy_idle:{vault['vault_address']}:{deploy_amount:.6f}",
                "type": "deploy_idle",
                "target_vault_address": vault["vault_address"],
                "target_vault_name": vault.get("vault_name"),
                "target_apy": vault.get("apy"),
                "amount_usd": deploy_amount,
                "annual_yield_gain_usd": annual_gain,
                "breakeven_days": breakeven,
                "estimated_cost": c,
            })

    max_rebalance_pct = float(dc.get("max_rebalance_pct", 50))
    allow_partial = bool(dc.get("allow_partial_rebalance", True))
    min_apy_improvement = float(dc.get("min_apy_improvement", 0.01))

    for position in positions:
        source_address = position["vault_address"]
        source_apy = float(position.get("apy", 0))
        source_balance = float(position.get("balance_usd", 0))
        if source_balance <= 0:
            continue
        for vault in opportunities[:10]:
            target_address = vault["vault_address"]
            if target_address == source_address:
                continue
            target_apy = float(vault.get("apy", 0))
            apy_delta = target_apy - source_apy
            if apy_delta < min_apy_improvement:
                continue

            full_amount = source_balance
            partial_amount = source_balance * (max_rebalance_pct / 100)
            amounts = [("rebalance", full_amount)]
            if allow_partial and partial_amount < full_amount:
                amounts.append(("partial_rebalance", partial_amount))

            for action_type, amount in amounts:
                if amount < min_deposit:
                    continue
                c = _cost(action_type, cfg)
                annual_gain = amount * apy_delta
                breakeven = _finite_days(c["tx_cost_usd"], annual_gain)
                candidates.append({
                    "id": f"{action_type}:{source_address}:{target_address}:{amount:.6f}",
                    "type": action_type,
                    "source_vault_address": source_address,
                    "source_vault_name": position.get("vault_name"),
                    "source_position_nickname": position.get("nickname"),
                    "source_apy": source_apy,
                    "target_vault_address": target_address,
                    "target_vault_name": vault.get("vault_name"),
                    "target_apy": target_apy,
                    "apy_delta": apy_delta,
                    "amount_usd": amount,
                    "annual_yield_gain_usd": annual_gain,
                    "breakeven_days": breakeven,
                    "estimated_cost": c,
                })

    return candidates


def build_decision_packet(agent, cfg: dict[str, Any], preference_name: str | None = None, intent: str | None = None) -> dict[str, Any]:
    resolved_cfg = apply_preference(cfg, preference_name)
    # Agent already owns clients; update its config criteria by reconstructing in CLI caller when preference is active.
    idle = agent.get_idle_assets()
    positions = agent.get_positions()
    opportunities = agent.get_opportunities()
    candidates = build_candidate_actions(agent, resolved_cfg, opportunities, positions, idle)
    return {
        "schema_version": PACKET_SCHEMA,
        "wallet": agent.wallet.address,
        "agent": resolved_cfg.get("agent", {}).get("name", "default"),
        "preference": preference_name,
        "intent": intent or "optimize net yield without excessive churn",
        "idle_assets": idle,
        "current_positions": positions,
        "eligible_vaults": opportunities,
        "candidate_actions": candidates,
        "constraints": {
            "must_choose_candidate_id": True,
            "preference_is_hard_boundary": True,
            "no_arbitrary_tx_data": True,
            "decision": decision_config(resolved_cfg),
            "agent_caps": {
                "max_deploy_usd": resolved_cfg.get("agent", {}).get("max_deploy_usd"),
                "max_position_pct": resolved_cfg.get("agent", {}).get("max_position_pct"),
            },
        },
    }


def normalize_decision(decision: dict[str, Any]) -> dict[str, Any]:
    if "schema_version" not in decision:
        decision = {"schema_version": DECISION_SCHEMA, **decision}
    return decision


def validate_decision(decision: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    decision = normalize_decision(decision)
    violations: list[str] = []
    if packet.get("schema_version") != PACKET_SCHEMA:
        violations.append("invalid packet schema_version")
    if decision.get("schema_version") != DECISION_SCHEMA:
        violations.append("invalid decision schema_version")

    candidate_id = decision.get("candidate_id")
    candidates = {c["id"]: c for c in packet.get("candidate_actions", [])}
    candidate = candidates.get(candidate_id)
    if not candidate:
        violations.append("candidate_id does not exist in packet")
        candidate = None

    if candidate:
        target = candidate.get("target_vault_address")
        if target:
            eligible = {v["vault_address"] for v in packet.get("eligible_vaults", [])}
            if target not in eligible:
                violations.append("target vault is not in eligible_vaults")
        source = candidate.get("source_vault_address")
        if source:
            sources = {p["vault_address"] for p in packet.get("current_positions", [])}
            if source not in sources:
                violations.append("source vault is not in current_positions")
        amount = float(candidate.get("amount_usd", 0))
        if amount < 0 or not math.isfinite(amount):
            violations.append("candidate amount is invalid")

        dc = packet.get("constraints", {}).get("decision", {})
        breakeven = candidate.get("breakeven_days")
        if candidate.get("type") != "hold" and breakeven is not None:
            if breakeven > float(dc.get("max_breakeven_days", 30)):
                violations.append("breakeven_days exceeds max_breakeven_days")
        if candidate.get("type") != "hold":
            net = float(candidate.get("annual_yield_gain_usd", 0)) - float(candidate.get("estimated_cost", {}).get("tx_cost_usd", 0))
            if net < float(dc.get("min_net_gain_usd", 1.0)):
                violations.append("net expected gain is below min_net_gain_usd")

    return {
        "valid": not violations,
        "violations": violations,
        "decision": decision,
        "candidate": candidate,
    }


def plan_decision(agent, decision: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    validation = validate_decision(decision, packet)
    if not validation["valid"]:
        return {"valid": False, "validation": validation, "transactions": [], "status": "invalid"}

    candidate = validation["candidate"]
    action = candidate["type"]
    if action == "hold":
        return {"valid": True, "validation": validation, "transactions": [], "status": "hold"}

    if action == "deploy_idle":
        plan = agent.prepare_deploy_to_vault(candidate["target_vault_address"], float(candidate["amount_usd"]))
        return {"valid": True, "validation": validation, "transactions": plan["transactions"], "status": "planned", "plan": plan}

    if action in {"rebalance", "partial_rebalance"}:
        redeem_plan = agent.prepare_redeem_by_vault(candidate["source_vault_address"], amount_usd=float(candidate["amount_usd"]))
        deploy_plan = agent.prepare_deploy_to_vault(candidate["target_vault_address"], float(candidate["amount_usd"]))
        transactions = redeem_plan["transactions"] + deploy_plan["transactions"]
        return {
            "valid": True,
            "validation": validation,
            "transactions": transactions,
            "status": "planned",
            "redeem_plan": redeem_plan,
            "deploy_plan": deploy_plan,
        }

    raise ValueError(f"unsupported candidate action: {action}")


def execute_decision(agent, decision: dict[str, Any], packet: dict[str, Any]) -> dict[str, Any]:
    plan = plan_decision(agent, decision, packet)
    if not plan.get("valid"):
        return plan
    if not plan.get("transactions"):
        return {**plan, "tx_hashes": [], "status": plan.get("status", "hold")}
    tx_hashes = agent.executor.execute_multiple(plan["transactions"])
    return {**plan, "tx_hashes": tx_hashes, "status": "submitted"}
