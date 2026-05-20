import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from agent.cli.main import app
from test_api_cli import API_COMMAND_CASES


runner = CliRunner()


EXPECTED_COMMAND_PATHS = {
    (),
    ("agent",),
    ("agent", "compare"),
    ("agent", "init"),
    ("agent", "list"),
    ("agent", "run"),
    ("agent", "show"),
    ("api",),
    ("api", "assets"),
    ("api", "assets", "list"),
    ("api", "benchmarks"),
    ("api", "benchmarks", "get"),
    ("api", "benchmarks", "history"),
    ("api", "curators"),
    ("api", "detailed-vaults"),
    ("api", "detailed-vaults", "apy"),
    ("api", "detailed-vaults", "get"),
    ("api", "detailed-vaults", "list"),
    ("api", "detailed-vaults", "tvl"),
    ("api", "health"),
    ("api", "historical"),
    ("api", "historical", "apy"),
    ("api", "historical", "asset-prices"),
    ("api", "historical", "share-price"),
    ("api", "historical", "tvl"),
    ("api", "historical", "vault"),
    ("api", "networks"),
    ("api", "nrt"),
    ("api", "nrt", "share-price"),
    ("api", "nrt", "total-assets"),
    ("api", "nrt", "total-supply"),
    ("api", "nrt", "underlying-asset-price"),
    ("api", "nrt", "vault"),
    ("api", "portfolio"),
    ("api", "portfolio", "best-deposit-options"),
    ("api", "portfolio", "best-vault"),
    ("api", "portfolio", "events"),
    ("api", "portfolio", "idle-assets"),
    ("api", "portfolio", "position"),
    ("api", "portfolio", "positions"),
    ("api", "portfolio", "total-returns"),
    ("api", "protocols"),
    ("api", "request"),
    ("api", "tags"),
    ("api", "transactions"),
    ("api", "transactions", "context"),
    ("api", "transactions", "payload"),
    ("api", "transactions", "rewards"),
    ("api", "transactions", "rewards", "claim"),
    ("api", "transactions", "rewards", "context"),
    ("api", "transactions", "suffix"),
    ("api", "vaults"),
    ("api", "vaults", "list"),
    ("config",),
    ("config", "path"),
    ("config", "set"),
    ("config", "show"),
    ("decision-packet",),
    ("deploy",),
    ("execute-decision",),
    ("idle",),
    ("opportunities",),
    ("plan-decision",),
    ("positions",),
    ("preference",),
    ("preference", "init"),
    ("preference", "list"),
    ("preference", "set"),
    ("preference", "show"),
    ("redeem",),
    ("redeem-all",),
    ("setup",),
    ("shell",),
    ("status",),
    ("validate-decision",),
    ("wallet",),
    ("wallet", "address"),
    ("wallet", "create"),
    ("wallet", "show"),
}


def command_tree():
    return get_command(app)


def collect_command_paths(command, prefix=()):
    paths = {prefix}
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            paths |= collect_command_paths(child, (*prefix, name))
    return paths


def command_leaf_paths(command, prefix=()):
    if not isinstance(command, click.Group):
        return {prefix}
    leaves = set()
    for name, child in command.commands.items():
        leaves |= command_leaf_paths(child, (*prefix, name))
    return leaves


def command_prefix(args, command):
    prefix = []
    current = command
    for arg in args:
        if not isinstance(current, click.Group) or arg not in current.commands:
            break
        prefix.append(arg)
        current = current.commands[arg]
    return tuple(prefix)


def test_command_inventory_matches_expected_tree():
    assert collect_command_paths(command_tree()) == EXPECTED_COMMAND_PATHS


@pytest.mark.parametrize("path", sorted(EXPECTED_COMMAND_PATHS))
def test_every_command_and_group_renders_help(monkeypatch, tmp_path, path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    args = [*path, "--help"] if path else ["--help"]

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.stdout
    assert "Usage:" in result.stdout


def test_api_endpoint_mapping_cases_cover_every_api_leaf_command():
    api_leaves = {
        path
        for path in command_leaf_paths(command_tree())
        if path[:1] == ("api",)
    }
    covered = {
        command_prefix(args, command_tree())
        for args, _, _ in API_COMMAND_CASES
    }

    assert covered == api_leaves
