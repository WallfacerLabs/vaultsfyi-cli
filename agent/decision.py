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
    "page",
    "per_page",
    "allowed_assets",
    "disallowed_assets",
    "allowed_networks",
    "disallowed_networks",
    "allowed_protocols",
    "disallowed_protocols",
    "min_apy",
    "max_apy",
    "min_tvl",
    "max_tvl",
    "min_vault_score",
    "apy_interval",
    "only_transactional",
    "only_app_featured",
    "allow_corrupted",
    "allow_vaults_with_warnings",
    "tags",
    "curators",
    "sort_order",
    "sort_by",
    "vault_whitelist",
    "blocked_protocols",
    "allowed_curators",
    "only_instant_deposit",
    "only_instant_redeem",
    "max_performance_fee",
    "max_management_fee",
    "max_withdrawal_fee",
    "max_deposit_fee",
    "min_remaining_capacity",
    "only_rewards_supported",
}

PREFERENCE_KEY_ALIASES = {
    "blocked_protocols": "disallowed_protocols",
    "allowed_curators": "curators",
}

BUCKET_MAX_PCT_KEYS = ("bucket_max_pct", "max_portfolio_pct")
BUCKET_TOLERANCE_PCT_KEYS = ("bucket_tolerance_pct", "tolerance_pct")


def _address_key(address: str | None) -> str:
    return (address or "").lower()


def _list_value(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str) and "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return value
    return None


def _percent_value(value: Any, key: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"preference {key} must be a number") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"preference {key} must be finite")
    return parsed


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
            target_key = PREFERENCE_KEY_ALIASES.get(key, key)
            if target_key != key and preference.get(target_key) not in (None, "", []):
                continue
            resolved.setdefault("strategy", {})[target_key] = value
    resolved.setdefault("active_preference", {})["name"] = preference_name
    resolved["active_preference"]["filters"] = preference
    return resolved


def preference_bucket_config(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Return active preference bucket settings, if the preference defines them."""
    active = cfg.get("active_preference") or {}
    preference = active.get("filters") or {}
    max_value = _first_present(preference, BUCKET_MAX_PCT_KEYS)
    if max_value is None:
        return None

    max_pct = _percent_value(max_value, "bucket_max_pct")
    tolerance_value = _first_present(preference, BUCKET_TOLERANCE_PCT_KEYS)
    tolerance_pct = (
        0.0
        if tolerance_value is None
        else _percent_value(tolerance_value, "bucket_tolerance_pct")
    )
    if max_pct < 0 or max_pct > 100:
        raise ValueError("preference bucket_max_pct must be between 0 and 100")
    if tolerance_pct < 0:
        raise ValueError("preference bucket_tolerance_pct must be greater than or equal to 0")
    return {
        "preference": active.get("name"),
        "max_pct": max_pct,
        "tolerance_pct": tolerance_pct,
        "upper_pct": min(100.0, max_pct + tolerance_pct),
    }


def preference_bucket_state(
    cfg: dict[str, Any],
    opportunities: list[dict],
    positions: list[dict],
    idle_assets: dict,
) -> dict[str, Any] | None:
    """Estimate active preference exposure from eligible vault and whitelist addresses."""
    bucket = preference_bucket_config(cfg)
    if bucket is None:
        return None

    active = cfg.get("active_preference") or {}
    preference = active.get("filters") or {}
    bucket_addresses = {
        _address_key(vault.get("vault_address"))
        for vault in opportunities
        if vault.get("vault_address")
    }
    bucket_addresses.update(
        _address_key(str(address))
        for address in _list_value(preference.get("vault_whitelist"))
        if address
    )

    bucket_usd = sum(
        float(position.get("balance_usd", 0))
        for position in positions
        if _address_key(position.get("vault_address")) in bucket_addresses
    )
    positions_usd = sum(float(position.get("balance_usd", 0)) for position in positions)
    idle_usd = float(idle_assets.get("usdc_balance", 0))
    portfolio_usd = idle_usd + positions_usd

    if portfolio_usd > 0:
        current_pct = (bucket_usd / portfolio_usd) * 100
        max_usd = portfolio_usd * (bucket["max_pct"] / 100)
        upper_usd = portfolio_usd * (bucket["upper_pct"] / 100)
    else:
        current_pct = 0.0
        max_usd = 0.0
        upper_usd = 0.0

    if current_pct > bucket["upper_pct"]:
        status = "over_tolerance"
    elif current_pct >= bucket["max_pct"]:
        status = "within_tolerance"
    else:
        status = "under_limit"

    return {
        **bucket,
        "current_usd": bucket_usd,
        "current_pct": current_pct,
        "portfolio_usd": portfolio_usd,
        "max_usd": max_usd,
        "upper_usd": upper_usd,
        "remaining_deploy_usd": max(0.0, max_usd - bucket_usd),
        "remaining_tolerance_usd": max(0.0, upper_usd - bucket_usd),
        "status": status,
        "matched_vault_addresses": sorted(bucket_addresses),
    }


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


def _candidate_increases_bucket_exposure(candidate: dict[str, Any], bucket: dict[str, Any]) -> bool:
    bucket_addresses = {_address_key(address) for address in bucket.get("matched_vault_addresses", [])}
    target = _address_key(candidate.get("target_vault_address"))
    if not target or target not in bucket_addresses:
        return False
    source = _address_key(candidate.get("source_vault_address"))
    return not source or source not in bucket_addresses


def _position_balances_by_address(positions: list[dict]) -> dict[str, float]:
    balances: dict[str, float] = {}
    for position in positions:
        key = _address_key(position.get("vault_address"))
        if key:
            balances[key] = balances.get(key, 0.0) + float(position.get("balance_usd", 0))
    return balances


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
    max_position_pct = cfg.get("agent", {}).get("max_position_pct")
    max_single = cfg.get("risk", {}).get("max_single_vault_usd")
    caps = [float(v) for v in [max_agent_deploy, max_single] if v is not None]
    portfolio_value = idle_usd + sum(float(position.get("balance_usd", 0)) for position in positions)
    position_cap_usd = None
    if max_position_pct is not None and portfolio_value > 0:
        position_cap_usd = portfolio_value * (float(max_position_pct) / 100)
        caps.append(position_cap_usd)
    deploy_amount = idle_usd if not caps else min(idle_usd, min(caps))
    bucket_state = preference_bucket_state(cfg, opportunities, positions, idle_assets)
    bucket_addresses = set(bucket_state["matched_vault_addresses"]) if bucket_state else set()
    if bucket_state:
        deploy_amount = min(deploy_amount, float(bucket_state["remaining_deploy_usd"]))
    existing_vault_addresses = {_address_key(position.get("vault_address")) for position in positions}
    position_balances = _position_balances_by_address(positions)
    max_single_usd = float(max_single) if max_single is not None else None

    for vault in opportunities[:10]:
        vault_address = vault.get("vault_address")
        if not vault_address or _address_key(vault_address) in existing_vault_addresses:
            continue
        if deploy_amount >= min_deposit:
            c = _cost("deploy_idle", cfg)
            annual_gain = deploy_amount * float(vault.get("apy", 0))
            breakeven = _finite_days(c["tx_cost_usd"], annual_gain)
            candidates.append({
                "id": f"deploy_idle:{vault_address}:{deploy_amount:.6f}",
                "type": "deploy_idle",
                "target_vault_address": vault_address,
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
        source_in_bucket = _address_key(source_address) in bucket_addresses if bucket_state else False
        source_apy = float(position.get("apy", 0))
        source_balance = float(position.get("balance_usd", 0))
        if source_balance <= 0:
            continue
        for vault in opportunities[:10]:
            target_address = vault["vault_address"]
            if _address_key(target_address) == _address_key(source_address):
                continue
            target_existing_usd = position_balances.get(_address_key(target_address), 0.0)
            target_capacity_limits = []
            if position_cap_usd is not None:
                target_capacity_limits.append(max(0.0, position_cap_usd - target_existing_usd))
            if max_single_usd is not None:
                target_capacity_limits.append(max(0.0, max_single_usd - target_existing_usd))
            target_capacity = min(target_capacity_limits) if target_capacity_limits else None
            target_apy = float(vault.get("apy", 0))
            apy_delta = target_apy - source_apy
            if apy_delta < min_apy_improvement:
                continue

            full_amount = source_balance
            partial_amount = source_balance * (max_rebalance_pct / 100)
            amounts = []
            if target_capacity is None or full_amount <= target_capacity:
                amounts.append(("rebalance", full_amount))
            if target_capacity is not None:
                partial_amount = min(partial_amount, target_capacity)
            if allow_partial and partial_amount < full_amount:
                amounts.append(("partial_rebalance", partial_amount))
            if bucket_state and not source_in_bucket:
                capacity = float(bucket_state["remaining_deploy_usd"])
                if capacity <= 0:
                    amounts = []
                else:
                    adjusted_amounts = []
                    seen_amounts = set()
                    for action_type, amount in amounts:
                        if amount <= capacity:
                            adjusted = (action_type, amount)
                        elif allow_partial:
                            adjusted = ("partial_rebalance", capacity)
                        else:
                            continue
                        key = (adjusted[0], round(float(adjusted[1]), 12))
                        if key not in seen_amounts:
                            adjusted_amounts.append(adjusted)
                            seen_amounts.add(key)
                    amounts = adjusted_amounts

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
    bucket_state = preference_bucket_state(resolved_cfg, opportunities, positions, idle)
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
            "preference_bucket": bucket_state,
            "decision": decision_config(resolved_cfg),
            "agent_caps": {
                "max_deploy_usd": resolved_cfg.get("agent", {}).get("max_deploy_usd"),
                "max_position_pct": resolved_cfg.get("agent", {}).get("max_position_pct"),
            },
            "risk_caps": {
                "max_single_vault_usd": resolved_cfg.get("risk", {}).get("max_single_vault_usd"),
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
        candidate_type = candidate.get("type")
        decision_action = decision.get("action")
        if not decision_action:
            violations.append("decision action is required")
        elif decision_action != candidate_type:
            violations.append("decision action does not match candidate type")
        if candidate_type not in {"hold", "deploy_idle", "rebalance", "partial_rebalance"}:
            violations.append("candidate type is unsupported")

        target = candidate.get("target_vault_address")
        if target:
            eligible = {_address_key(v.get("vault_address")) for v in packet.get("eligible_vaults", [])}
            if _address_key(target) not in eligible:
                violations.append("target vault is not in eligible_vaults")
        source = candidate.get("source_vault_address")
        if source:
            sources = {_address_key(p.get("vault_address")) for p in packet.get("current_positions", [])}
            if _address_key(source) not in sources:
                violations.append("source vault is not in current_positions")
        try:
            amount = float(candidate.get("amount_usd", 0))
        except (TypeError, ValueError):
            amount = math.nan
        if amount < 0 or not math.isfinite(amount):
            violations.append("candidate amount is invalid")
        elif candidate_type != "hold" and amount <= 0:
            violations.append("candidate amount must be positive")
        bucket = packet.get("constraints", {}).get("preference_bucket")
        if bucket and candidate_type != "hold" and _candidate_increases_bucket_exposure(candidate, bucket):
            try:
                remaining_bucket_usd = float(bucket.get("remaining_deploy_usd", 0))
            except (TypeError, ValueError):
                violations.append("preference bucket remaining deploy capacity is invalid")
                remaining_bucket_usd = math.nan
            if math.isfinite(remaining_bucket_usd) and amount > remaining_bucket_usd + 1e-9:
                violations.append("candidate exceeds preference bucket remaining deploy capacity")

        if target and candidate_type != "hold" and math.isfinite(amount):
            constraints = packet.get("constraints", {})
            target_limits = []
            positions = packet.get("current_positions", [])
            idle_assets = packet.get("idle_assets", {})
            try:
                target_existing_usd = _position_balances_by_address(positions).get(_address_key(target), 0.0)
            except (TypeError, ValueError):
                violations.append("current position balance is invalid")
                target_existing_usd = math.nan
            try:
                portfolio_usd = (
                    float(idle_assets.get("usdc_balance", 0))
                    + sum(float(position.get("balance_usd", 0)) for position in positions)
                )
            except (TypeError, ValueError):
                violations.append("portfolio value is invalid")
                portfolio_usd = math.nan
            max_position_pct = constraints.get("agent_caps", {}).get("max_position_pct")
            if max_position_pct is not None and math.isfinite(portfolio_usd):
                try:
                    target_limits.append(portfolio_usd * (float(max_position_pct) / 100))
                except (TypeError, ValueError):
                    violations.append("max_position_pct is invalid")
            max_single = constraints.get("risk_caps", {}).get("max_single_vault_usd")
            if max_single is not None:
                try:
                    target_limits.append(float(max_single))
                except (TypeError, ValueError):
                    violations.append("max_single_vault_usd is invalid")
            if target_limits and math.isfinite(target_existing_usd) and target_existing_usd + amount > min(target_limits) + 1e-9:
                violations.append("candidate exceeds target vault allocation cap")

        dc = packet.get("constraints", {}).get("decision", {})
        breakeven = candidate.get("breakeven_days")
        if candidate.get("type") != "hold" and breakeven is not None:
            try:
                breakeven_value = float(breakeven)
            except (TypeError, ValueError):
                violations.append("breakeven_days is invalid")
                breakeven_value = None
            if breakeven_value is not None and breakeven_value > float(dc.get("max_breakeven_days", 30)):
                violations.append("breakeven_days exceeds max_breakeven_days")
        if candidate.get("type") != "hold":
            try:
                net = float(candidate.get("annual_yield_gain_usd", 0)) - float(candidate.get("estimated_cost", {}).get("tx_cost_usd", 0))
            except (TypeError, ValueError):
                violations.append("net expected gain is invalid")
                net = None
            if net is not None and net < float(dc.get("min_net_gain_usd", 1.0)):
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
        amount_usd = float(candidate["amount_usd"])
        idle_usd = float(packet.get("idle_assets", {}).get("usdc_balance", 0))
        redeem_plan = agent.prepare_redeem_by_vault(candidate["source_vault_address"], amount_usd=amount_usd)
        deploy_plan = agent.prepare_deploy_to_vault(
            candidate["target_vault_address"],
            amount_usd,
            available_usd=idle_usd + amount_usd,
        )
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
