"""vaultsfyi command-line interface."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path
from typing import Optional

import click
import typer
from ows import create_wallet, get_wallet
from typer.main import get_command

from agent.cli import config as config_mod
from agent.cli.context import CliContext, build_context
from agent.cli.output import OutputFormat, confirm_or_abort, echo_error, echo_json, format_apy, format_usd, print_table

app = typer.Typer(help="vaults.fyi DeFi vault manager")
wallet_app = typer.Typer(help="Manage the configured OWS wallet")
config_app = typer.Typer(help="Manage vaultsfyi CLI config")
app.add_typer(wallet_app, name="wallet")
app.add_typer(config_app, name="config")


def _ctx() -> CliContext:
    ctx = click.get_current_context()
    return ctx.obj


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(OutputFormat.table, "--output", "-o", help="Output format: table or json"),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config.toml"),
):
    """Command-line DeFi vault manager powered by vaults.fyi."""
    ctx.obj = build_context(output, config)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _run(fn):
    ctx = _ctx()
    try:
        return fn(ctx)
    except typer.Abort:
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
def opportunities(limit: int = typer.Option(10, "--limit", "-l", help="Max rows to show")):
    """Show current deposit opportunities."""
    def inner(ctx: CliContext):
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
    yes: bool = typer.Option(False, "--yes", "-y", help="Broadcast without interactive confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build and print the plan without broadcasting"),
):
    """Deploy a percentage of idle USDC to the selected vault."""
    def inner(ctx: CliContext):
        agent = ctx.agent()
        plan = agent.prepare_deploy(percent)
        if dry_run:
            result = {**plan, "status": "dry_run"}
        else:
            if ctx.output == OutputFormat.table:
                typer.echo(f"Deploy {format_usd(plan['amount_usd'], agent.display_decimals)} to {plan['vault']['vault_name']}")
                typer.echo(f"Transactions: {plan['transaction_count']}")
            confirm_or_abort("Broadcast these transaction(s)?", yes, ctx.output)
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
def config_show():
    """Show effective configuration."""
    ctx = _ctx()
    if ctx.output == OutputFormat.json:
        echo_json(ctx.cfg)
    else:
        rows = []
        for section, values in ctx.cfg.items():
            if isinstance(values, dict):
                for key, value in values.items():
                    display_value = "***" if key in {"api_key"} and value else value
                    rows.append({"key": f"{section}.{key}", "value": display_value})
        print_table(rows)


@config_app.command("path")
def config_path():
    """Print the active config path."""
    ctx = _ctx()
    path = ctx.config_path or config_mod.default_config_path()
    if ctx.output == OutputFormat.json:
        echo_json({"path": str(path)})
    else:
        typer.echo(path)


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a config value, e.g. vaults.api_key or wallet.name."""
    def inner(ctx: CliContext):
        config_mod.set_config_value(ctx.cfg, key, value)
        path = config_mod.write_config(ctx.cfg, ctx.config_path)
        if ctx.output == OutputFormat.json:
            echo_json({"path": str(path), "key": key, "value": value})
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
