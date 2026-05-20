"""vaultsfyi command-line interface."""

from __future__ import annotations

import shlex
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import click
import fcntl
import typer
from ows import create_wallet, get_wallet
from typer.main import get_command

from agent.cli.api import api_app
from agent.cli import config as config_mod
from agent.cli.context import CliContext, build_context
from agent.cli.output import OutputFormat, confirm_or_abort, echo_error, echo_json, format_apy, format_usd, print_table
from agent.decision import (
    build_decision_packet,
    execute_decision,
    plan_decision,
    preference_bucket_config,
    preference_bucket_state,
    read_json,
    validate_decision,
)

app = typer.Typer(help="vaults.fyi DeFi vault manager")
wallet_app = typer.Typer(help="Manage the configured OWS wallet")
config_app = typer.Typer(help="Manage vaultsfyi CLI config")
agent_app = typer.Typer(help="Manage named strategy agents")
preference_app = typer.Typer(help="Manage reusable vault preference filters")
app.add_typer(wallet_app, name="wallet")
app.add_typer(config_app, name="config")
app.add_typer(agent_app, name="agent")
app.add_typer(preference_app, name="preference")
app.add_typer(api_app, name="api")


def _ctx() -> CliContext:
    ctx = click.get_current_context()
    return ctx.obj


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(OutputFormat.table, "--output", "-o", help="Output format: table or json"),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config.toml"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Optional named strategy profile"),
):
    """Command-line DeFi vault manager powered by vaults.fyi."""
    ctx.obj = build_context(output, config, agent)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _run(fn):
    ctx = _ctx()
    try:
        return fn(ctx)
    except typer.Abort:
        raise
    except typer.Exit:
        raise
    except Exception as exc:
        echo_error(exc, ctx.output)
        raise typer.Exit(1)


def _state_row(state: dict) -> dict:
    return {
        "wallet": state["wallet"],
        "network": state["network"],
        "asset": state["asset"],
        "gas_eth": f"{state['gas']['balance_eth']:.6f}",
        "idle_usdc": format_usd(state["idle_assets"]["usdc_balance"]),
        "positions": state["positions_count"],
    }


def _effective_deploy_percent(ctx: CliContext, agent, requested_percent: float) -> float:
    caps = [
        ctx.cfg.get("agent", {}).get("max_deploy_usd"),
        ctx.cfg.get("risk", {}).get("max_single_vault_usd"),
    ]
    caps = [float(cap) for cap in caps if cap is not None]
    max_position_pct = ctx.cfg.get("agent", {}).get("max_position_pct")
    bucket_cfg = preference_bucket_config(ctx.cfg)
    if not caps and max_position_pct is None and bucket_cfg is None:
        return requested_percent

    idle_info = agent.get_idle_assets()
    idle = idle_info["usdc_balance"]
    positions = None
    if max_position_pct is not None:
        positions = agent.get_positions()
        positions_value = sum(float(position.get("balance_usd", 0)) for position in positions)
        portfolio_value = idle + positions_value
        if portfolio_value > 0:
            caps.append(portfolio_value * (float(max_position_pct) / 100))
    if bucket_cfg is not None:
        positions = positions if positions is not None else agent.get_positions()
        bucket_state = preference_bucket_state(ctx.cfg, agent.get_opportunities(), positions, idle_info)
        if bucket_state is not None:
            caps.append(float(bucket_state["remaining_deploy_usd"]))
    if not caps:
        return requested_percent
    if idle <= 0:
        return requested_percent
    requested_usd = idle * (requested_percent / 100)
    capped_usd = min(requested_usd, min(caps))
    return max(0.0, min(100.0, (capped_usd / idle) * 100))


@contextmanager
def _wallet_lock(ctx: CliContext):
    wallet_name = ctx.cfg["wallet"]["name"]
    locks_dir = config_mod.locks_dir()
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = locks_dir / f"{wallet_name}.lock"
    with lock_path.open("w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"wallet '{wallet_name}' is already locked by another vaultsfyi process") from exc
        lock_file.write(f"agent={ctx.effective_agent_name}\n")
        lock_file.flush()
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


@app.command()
def status():
    """Show wallet, gas, idle USDC, and position count."""
    def inner(ctx: CliContext):
        state = ctx.agent().get_state()
        if ctx.output == OutputFormat.json:
            echo_json(state)
        else:
            print_table([_state_row(state)])
    _run(inner)


@app.command()
def idle():
    """Show idle USDC balance."""
    def inner(ctx: CliContext):
        data = ctx.agent().get_idle_assets()
        if ctx.output == OutputFormat.json:
            echo_json(data)
        else:
            print_table([{"asset": "USDC", "balance": format_usd(data["usdc_balance"]), "tokens": data["balance_tokens"]}])
    _run(inner)


@app.command()
def positions():
    """Show active vault positions."""
    def inner(ctx: CliContext):
        agent = ctx.agent()
        data = agent.get_positions()
        if ctx.output == OutputFormat.json:
            echo_json(data)
        else:
            rows = [
                {
                    "nickname": p["nickname"],
                    "vault": p["vault_name"],
                    "asset": p["asset"],
                    "apy": format_apy(p["apy"]),
                    "balance": format_usd(p["balance_usd"], agent.display_decimals),
                }
                for p in data
            ]
            print_table(rows)
    _run(inner)


@app.command()
def opportunities(
    limit: int = typer.Option(10, "--limit", "-l", help="Max rows to show"),
    preference: Optional[str] = typer.Option(None, "--preference", "-p", help="Optional named preference filter"),
):
    """Show current deposit opportunities."""
    def inner(ctx: CliContext):
        ctx = ctx.with_preference(preference)
        data = ctx.agent().get_opportunities()[:limit]
        if ctx.output == OutputFormat.json:
            echo_json(data)
        else:
            rows = [
                {
                    "vault": o["vault_name"],
                    "apy": format_apy(o["apy"]),
                    "tvl": format_usd(o["tvl"], 0),
                    "network": o["network"],
                    "asset": o["asset"],
                    "address": o["vault_address"],
                }
                for o in data
            ]
            print_table(rows)
    _run(inner)


@app.command()
def deploy(
    percent: float = typer.Option(..., "--percent", "-p", help="Percent of idle USDC to deploy"),
    preference: Optional[str] = typer.Option(None, "--preference", help="Optional named preference filter"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Broadcast without interactive confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build and print the plan without broadcasting"),
):
    """Deploy a percentage of idle USDC to the selected vault."""
    def inner(ctx: CliContext):
        ctx = ctx.with_preference(preference)
        agent = ctx.agent()
        deploy_percent = _effective_deploy_percent(ctx, agent, percent)
        if percent > 0 and deploy_percent <= 0 and preference_bucket_config(ctx.cfg):
            bucket_name = ctx.cfg.get("active_preference", {}).get("name") or preference
            raise ValueError(f"preference bucket '{bucket_name}' has no remaining deploy capacity")
        plan = agent.prepare_deploy(deploy_percent)
        if dry_run:
            result = {**plan, "status": "dry_run"}
        else:
            if ctx.output == OutputFormat.table:
                typer.echo(f"Deploy {format_usd(plan['amount_usd'], agent.display_decimals)} to {plan['vault']['vault_name']}")
                typer.echo(f"Transactions: {plan['transaction_count']}")
            confirm_or_abort("Broadcast these transaction(s)?", yes, ctx.output)
            with _wallet_lock(ctx):
                result = agent.execute_deploy_plan(plan)
        if ctx.output == OutputFormat.json:
            echo_json(result)
        else:
            rows = [{
                "status": result["status"],
                "vault": result["vault"]["vault_name"],
                "amount": format_usd(result["amount_usd"], agent.display_decimals),
                "tx_hashes": ", ".join(result.get("tx_hashes", [])) or "—",
            }]
            print_table(rows)
    _run(inner)


@app.command()
def redeem(
    position: str = typer.Option(..., "--position", help="Position nickname"),
    percent: float = typer.Option(100.0, "--percent", "-p", help="Percent to redeem"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Broadcast without interactive confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build and print the plan without broadcasting"),
):
    """Redeem from a vault position by nickname."""
    def inner(ctx: CliContext):
        agent = ctx.agent()
        plan = agent.prepare_redeem(position, percent)
        if dry_run:
            result = {**plan, "status": "dry_run"}
        else:
            if ctx.output == OutputFormat.table:
                typer.echo(f"Redeem {format_usd(plan['amount_usd'], agent.display_decimals)} from {plan['position']['vault_name']}")
                typer.echo(f"Transactions: {plan['transaction_count']}")
            confirm_or_abort("Broadcast these transaction(s)?", yes, ctx.output)
            with _wallet_lock(ctx):
                result = agent.execute_redeem_plan(plan)
        if ctx.output == OutputFormat.json:
            echo_json(result)
        else:
            print_table([{
                "status": result["status"],
                "position": result["position"]["nickname"],
                "vault": result["position"]["vault_name"],
                "amount": format_usd(result["amount_usd"], agent.display_decimals),
                "tx_hashes": ", ".join(result.get("tx_hashes", [])) or "—",
            }])
    _run(inner)


@app.command("redeem-all")
def redeem_all(
    yes: bool = typer.Option(False, "--yes", "-y", help="Broadcast without interactive confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build and print plans without broadcasting"),
):
    """Redeem all active positions."""
    def inner(ctx: CliContext):
        agent = ctx.agent()
        positions_data = agent.get_positions()
        plans = [agent.prepare_redeem(p["nickname"], 100.0) for p in positions_data]
        if dry_run:
            results = [{**plan, "status": "dry_run"} for plan in plans]
        else:
            if ctx.output == OutputFormat.table:
                typer.echo(f"Redeem all positions: {len(plans)} plan(s)")
            confirm_or_abort("Broadcast all redemption transaction(s)?", yes, ctx.output)
            with _wallet_lock(ctx):
                results = [agent.execute_redeem_plan(plan) for plan in plans]
        if ctx.output == OutputFormat.json:
            echo_json(results)
        else:
            rows = [
                {
                    "status": r["status"],
                    "position": r["position"]["nickname"],
                    "vault": r["position"]["vault_name"],
                    "amount": format_usd(r["amount_usd"], agent.display_decimals),
                    "tx_hashes": ", ".join(r.get("tx_hashes", [])) or "—",
                }
                for r in results
            ]
            print_table(rows)
    _run(inner)


@app.command()
def setup(
    wallet_name: str = typer.Option("agent-treasury", "--wallet", help="OWS wallet name"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Optional vaults.fyi API key"),
):
    """Create user-level config and point it at an OWS wallet."""
    def inner(ctx: CliContext):
        cfg = config_mod.load_config(ctx.config_path)
        cfg["wallet"]["name"] = wallet_name
        cfg["wallet"]["chain"] = "base"
        if api_key:
            cfg["vaults"]["api_key"] = api_key
        path = config_mod.write_config(cfg, ctx.config_path)
        ows_cli = shutil.which("ows")
        if ctx.output == OutputFormat.json:
            echo_json({"config_path": str(path), "wallet": wallet_name, "ows_cli_found": bool(ows_cli)})
        else:
            typer.echo(f"Config written: {path}")
            typer.echo(f"Wallet: {wallet_name}")
            typer.echo("OWS CLI: " + (ows_cli or "not found on PATH"))
            typer.echo("Next: `vaultsfyi wallet create` or import with `ows wallet import`, then `vaultsfyi status`.")
    _run(inner)


@agent_app.command("init")
def agent_init(
    name: str = typer.Argument(..., help="Agent profile name"),
    wallet: Optional[str] = typer.Option(None, "--wallet", help="OWS wallet name, defaults to agent name"),
    mode: str = typer.Option("dry-run", "--mode", help="dry-run, paper, or live"),
):
    """Create a named agent strategy profile."""
    def inner(ctx: CliContext):
        path = config_mod.agent_config_path(name)
        if path.exists():
            raise ValueError(f"agent profile '{name}' already exists at {path}")
        profile = config_mod.new_agent_profile(name, wallet, mode)
        path = config_mod.write_agent_profile(name, profile)
        payload = {"name": name, "wallet": profile["wallet"]["name"], "mode": mode, "path": str(path)}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
            typer.echo(f"Next: vaultsfyi --agent {name} wallet create")
    _run(inner)


@agent_app.command("list")
def agent_list():
    """List configured agent profiles."""
    ctx = _ctx()
    rows = config_mod.list_agent_profiles()
    if ctx.output == OutputFormat.json:
        echo_json(rows)
    else:
        print_table(rows)


@agent_app.command("show")
def agent_show(name: Optional[str] = typer.Argument(None, help="Agent profile name, defaults to --agent")):
    """Show an effective agent profile config."""
    def inner(ctx: CliContext):
        agent_name = name or ctx.agent_name
        if not agent_name:
            raise ValueError("provide an agent name or use --agent")
        cfg = config_mod.load_config(ctx.config_path, agent_name)
        if ctx.output == OutputFormat.json:
            echo_json(config_mod.sanitize_config(cfg))
        else:
            rows = []
            for section, values in cfg.items():
                if isinstance(values, dict):
                    for key, value in values.items():
                        display_value = "***" if key in {"api_key"} and value else value
                        rows.append({"key": f"{section}.{key}", "value": display_value})
            print_table(rows)
    _run(inner)


def _agent_run_payload(ctx: CliContext, deploy_percent: float | None = None) -> dict:
    agent = ctx.agent()
    state = agent.get_state()
    opportunities = agent.get_opportunities()
    top = opportunities[0] if opportunities else None
    payload = {
        "agent": ctx.effective_agent_name,
        "wallet": ctx.cfg["wallet"]["name"],
        "mode": ctx.cfg["agent"].get("mode", "dry-run"),
        "state": state,
        "top_opportunity": top,
        "opportunities_count": len(opportunities),
    }
    if deploy_percent is not None:
        try:
            deploy_percent = _effective_deploy_percent(ctx, agent, deploy_percent)
            payload["plan"] = agent.prepare_deploy(deploy_percent)
            payload["plan"]["status"] = "dry_run"
        except Exception as exc:
            payload["plan_error"] = str(exc)
    return payload


@agent_app.command("run")
def agent_run(
    name: str = typer.Argument(..., help="Agent profile name"),
    once: bool = typer.Option(True, "--once", help="Run one strategy pass"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Never broadcast; build a dry-run plan when possible"),
    execute: bool = typer.Option(False, "--execute", help="Allow live deploy if profile mode is live"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Required with --execute to broadcast"),
):
    """Run one named agent strategy pass."""
    def inner(ctx: CliContext):
        if not once:
            raise ValueError("loop mode is not implemented yet; use an external scheduler for now")
        run_ctx = build_context(ctx.output, ctx.config_path, name)
        mode = run_ctx.cfg["agent"].get("mode", "dry-run")
        deploy_percent = float(run_ctx.cfg.get("execution", {}).get("deploy_percent", 10.0))
        should_plan = dry_run or mode in {"dry-run", "paper"} or execute
        payload = _agent_run_payload(run_ctx, deploy_percent if should_plan else None)

        if execute:
            if mode != "live":
                raise ValueError(f"agent '{name}' mode is {mode}; set mode='live' before executing")
            if "plan" not in payload:
                raise ValueError(payload.get("plan_error", "could not build deploy plan"))
            confirm_or_abort(f"Broadcast agent '{name}' deploy transaction(s)?", yes, run_ctx.output)
            with _wallet_lock(run_ctx):
                payload["execution"] = run_ctx.agent().execute_deploy_plan(payload["plan"])

        if run_ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            row = {
                "agent": payload["agent"],
                "wallet": payload["wallet"],
                "mode": payload["mode"],
                "idle": format_usd(payload["state"]["idle_assets"]["usdc_balance"]),
                "positions": payload["state"]["positions_count"],
                "top_vault": payload["top_opportunity"]["vault_name"] if payload["top_opportunity"] else "—",
                "top_apy": format_apy(payload["top_opportunity"]["apy"]) if payload["top_opportunity"] else "—",
                "plan": payload.get("plan", {}).get("status") or payload.get("plan_error", "—"),
            }
            print_table([row])
    _run(inner)


@agent_app.command("compare")
def agent_compare(names: list[str] = typer.Argument(..., help="Agent profile names to compare")):
    """Compare top opportunity and wallet state across profiles."""
    def inner(ctx: CliContext):
        rows = []
        payload = []
        for name in names:
            run_ctx = build_context(ctx.output, ctx.config_path, name)
            data = _agent_run_payload(run_ctx, None)
            payload.append(data)
            top = data["top_opportunity"]
            rows.append({
                "agent": name,
                "wallet": data["wallet"],
                "mode": data["mode"],
                "idle": format_usd(data["state"]["idle_assets"]["usdc_balance"]),
                "positions": data["state"]["positions_count"],
                "top_vault": top["vault_name"] if top else "—",
                "top_apy": format_apy(top["apy"]) if top else "—",
            })
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table(rows)
    _run(inner)


@preference_app.command("init")
def preference_init(name: str = typer.Argument(..., help="Preference name")):
    """Create a reusable preference filter."""
    def inner(ctx: CliContext):
        path = config_mod.agent_config_path(ctx.agent_name) if ctx.agent_name else (ctx.config_path or config_mod.default_config_path())
        cfg = config_mod.load_toml(path) if path.exists() else {}
        prefs = cfg.setdefault("preferences", {})
        if name in prefs:
            raise ValueError(f"preference '{name}' already exists")
        prefs[name] = config_mod.new_preference()
        path = config_mod.write_toml_path(path, cfg)
        payload = {"name": name, "path": str(path), **prefs[name]}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
    _run(inner)


@preference_app.command("list")
def preference_list():
    """List reusable preference filters."""
    ctx = _ctx()
    rows = config_mod.list_preferences(ctx.cfg)
    if ctx.output == OutputFormat.json:
        echo_json(rows)
    else:
        print_table(rows)


@preference_app.command("show")
def preference_show(name: str = typer.Argument(..., help="Preference name")):
    """Show one preference filter."""
    def inner(ctx: CliContext):
        pref = ctx.cfg.get("preferences", {}).get(name)
        if pref is None:
            raise ValueError(f"preference '{name}' does not exist")
        payload = {"name": name, **pref}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
    _run(inner)


@preference_app.command("set")
def preference_set(name: str, key: str, value: str):
    """Set a preference value, e.g. min_tvl 10000000."""
    def inner(ctx: CliContext):
        path = config_mod.agent_config_path(ctx.agent_name) if ctx.agent_name else (ctx.config_path or config_mod.default_config_path())
        cfg = config_mod.load_toml(path) if path.exists() else {}
        prefs = cfg.setdefault("preferences", {})
        if name not in prefs:
            raise ValueError(f"preference '{name}' does not exist")
        prefs[name][key] = config_mod.parse_config_value(value)
        path = config_mod.write_toml_path(path, cfg)
        payload = {"name": name, "key": key, "value": prefs[name][key], "path": str(path)}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
    _run(inner)


@app.command("decision-packet")
def decision_packet(
    preference: Optional[str] = typer.Option(None, "--preference", "-p", help="Optional named preference filter"),
    intent: Optional[str] = typer.Option(None, "--intent", help="Allocator intent included in the packet"),
):
    """Emit a read-only packet for OpenClaw or another allocator."""
    def inner(ctx: CliContext):
        ctx = ctx.with_preference(preference)
        packet = build_decision_packet(ctx.agent(), ctx.cfg, preference, intent)
        echo_json(packet)
    _run(inner)


@app.command("validate-decision")
def validate_decision_cmd(
    decision: Path = typer.Argument(..., help="Decision JSON file"),
    packet: Path = typer.Option(..., "--packet", help="Decision packet JSON file"),
):
    """Validate an external allocator decision against a packet."""
    def inner(ctx: CliContext):
        result = validate_decision(read_json(decision), read_json(packet))
        if ctx.output == OutputFormat.json:
            echo_json(result)
        else:
            print_table([{"valid": result["valid"], "violations": "; ".join(result["violations"]) or "—"}])
        if not result["valid"]:
            raise typer.Exit(1)
    _run(inner)


@app.command("plan-decision")
def plan_decision_cmd(
    decision: Path = typer.Argument(..., help="Decision JSON file"),
    packet: Path = typer.Option(..., "--packet", help="Decision packet JSON file"),
):
    """Build an unsigned transaction plan from a validated decision."""
    def inner(ctx: CliContext):
        result = plan_decision(ctx.agent(), read_json(decision), read_json(packet))
        if ctx.output == OutputFormat.json:
            echo_json(result)
        else:
            print_table([{"status": result["status"], "valid": result.get("valid"), "transactions": len(result.get("transactions", []))}])
        if not result.get("valid"):
            raise typer.Exit(1)
    _run(inner)


@app.command("execute-decision")
def execute_decision_cmd(
    decision: Path = typer.Argument(..., help="Decision JSON file"),
    packet: Path = typer.Option(..., "--packet", help="Decision packet JSON file"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Broadcast without interactive confirmation"),
):
    """Validate, plan, sign, and broadcast a decision through OWS."""
    def inner(ctx: CliContext):
        decision_data = read_json(decision)
        packet_data = read_json(packet)
        validation = validate_decision(decision_data, packet_data)
        if not validation["valid"]:
            if ctx.output == OutputFormat.json:
                echo_json({"valid": False, "validation": validation, "status": "invalid"})
            else:
                print_table([{"status": "invalid", "violations": "; ".join(validation["violations"]) or "—"}])
            raise typer.Exit(1)
        confirm_or_abort("Broadcast transaction(s) for this decision?", yes, ctx.output)
        with _wallet_lock(ctx):
            result = execute_decision(ctx.agent(), decision_data, packet_data)
        if ctx.output == OutputFormat.json:
            echo_json(result)
        else:
            print_table([{"status": result["status"], "valid": result.get("valid"), "tx_hashes": ", ".join(result.get("tx_hashes", [])) or "—"}])
        if not result.get("valid", True):
            raise typer.Exit(1)
    _run(inner)


@app.command()
def shell():
    """Launch an interactive vaultsfyi command shell."""
    click_cmd = get_command(app)
    typer.echo("vaultsfyi shell. Type 'help' for commands, 'exit' to quit.")
    while True:
        try:
            line = input("vaultsfyi> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        if line == "help":
            line = "--help"
        args = shlex.split(line)
        try:
            click_cmd.main(args=args, prog_name="vaultsfyi", standalone_mode=False)
        except SystemExit:
            pass
        except Exception as exc:
            typer.echo(f"Error: {exc}", err=True)


@wallet_app.command("create")
def wallet_create(
    name: Optional[str] = typer.Option(None, "--name", help="Wallet name, defaults to config wallet.name"),
    passphrase: Optional[str] = typer.Option(None, "--passphrase", help="Optional wallet passphrase"),
):
    """Create the configured OWS wallet if it does not already exist."""
    def inner(ctx: CliContext):
        cfg = ctx.cfg
        wallet_name = name or cfg["wallet"]["name"]
        vault_path = cfg["wallet"].get("vault_path")
        created = False
        try:
            wallet = get_wallet(wallet_name, vault_path_opt=vault_path)
        except Exception:
            wallet = create_wallet(wallet_name, passphrase=passphrase, vault_path_opt=vault_path)
            created = True
        cfg["wallet"]["name"] = wallet_name
        path = config_mod.write_config(cfg, ctx.config_path)
        evm = next(a for a in wallet["accounts"] if a["chain_id"].startswith("eip155:"))
        payload = {"created": created, "wallet": wallet_name, "wallet_id": wallet["id"], "address": evm["address"], "config_path": str(path)}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
    _run(inner)


@wallet_app.command("show")
def wallet_show():
    """Show configured OWS wallet details."""
    def inner(ctx: CliContext):
        cfg = ctx.cfg
        wallet_name = cfg["wallet"]["name"]
        vault_path = cfg["wallet"].get("vault_path")
        wallet = get_wallet(wallet_name, vault_path_opt=vault_path)
        evm = next(a for a in wallet["accounts"] if a["chain_id"].startswith("eip155:"))
        payload = {"wallet": wallet_name, "wallet_id": wallet["id"], "address": evm["address"], "vault_path": vault_path or "~/.ows"}
        if ctx.output == OutputFormat.json:
            echo_json(payload)
        else:
            print_table([payload])
    _run(inner)


@wallet_app.command("address")
def wallet_address():
    """Print the configured EVM wallet address."""
    def inner(ctx: CliContext):
        cfg = ctx.cfg
        wallet = get_wallet(cfg["wallet"]["name"], vault_path_opt=cfg["wallet"].get("vault_path"))
        evm = next(a for a in wallet["accounts"] if a["chain_id"].startswith("eip155:"))
        if ctx.output == OutputFormat.json:
            echo_json({"address": evm["address"]})
        else:
            typer.echo(evm["address"])
    _run(inner)


@config_app.command("show")
def config_show(show_all: bool = typer.Option(False, "--all", help="Show advanced/multi-agent defaults too")):
    """Show effective configuration."""
    ctx = _ctx()
    cfg = config_mod.sanitize_config(ctx.cfg)
    if not show_all and not ctx.agent_name:
        cfg = {k: v for k, v in cfg.items() if k in {"wallet", "network", "vaults", "strategy", "display"}}
    if ctx.output == OutputFormat.json:
        echo_json(cfg)
    else:
        rows = []
        for section, values in cfg.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    rows.append({"key": f"{section}.{key}", "value": value})
        print_table(rows)


@config_app.command("path")
def config_path():
    """Print the active config path."""
    ctx = _ctx()
    path = config_mod.agent_config_path(ctx.agent_name) if ctx.agent_name else (ctx.config_path or config_mod.default_config_path())
    if ctx.output == OutputFormat.json:
        echo_json({"path": str(path)})
    else:
        typer.echo(path)


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a config value, e.g. vaults.api_key or wallet.name."""
    def inner(ctx: CliContext):
        parsed_value = config_mod.parse_config_value(value)
        if ctx.agent_name:
            path = config_mod.set_config_file_value(config_mod.agent_config_path(ctx.agent_name), key, parsed_value)
        else:
            path = config_mod.set_config_file_value(ctx.config_path or config_mod.default_config_path(), key, parsed_value)
        if ctx.output == OutputFormat.json:
            echo_json({"path": str(path), "key": key, "value": parsed_value})
        else:
            typer.echo(f"Set {key} in {path}")
    _run(inner)


def main(argv: list[str] | None = None) -> int:
    try:
        app(args=argv)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)


if __name__ == "__main__":
    sys.exit(main())
