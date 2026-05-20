import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RUN_E2E = os.getenv("VAULTSFYI_RUN_E2E") == "1" or os.getenv("VAULTSFYI_RUN_E2E_FULL") == "1"
RUN_FULL_E2E = os.getenv("VAULTSFYI_RUN_E2E_FULL") == "1"
API_KEY = os.getenv("VAULTS_API_KEY")
DEFAULT_USER = "0x" + "1" * 40
USER_ADDRESS = os.getenv("VAULTSFYI_E2E_USER_ADDRESS") or DEFAULT_USER
RATE_LIMIT_SECONDS = float(os.getenv("VAULTSFYI_E2E_RATE_LIMIT_SECONDS", "6.5"))
LAST_LIVE_CALL = 0.0

pytestmark = pytest.mark.e2e


def require_live_e2e(full: bool = False) -> None:
    if full and not RUN_FULL_E2E:
        pytest.skip("set VAULTSFYI_RUN_E2E_FULL=1 to run the full live API sweep")
    if not full and not RUN_E2E:
        pytest.skip("set VAULTSFYI_RUN_E2E=1 to run live CLI e2e tests")
    if not API_KEY:
        pytest.skip("set VAULTS_API_KEY in the environment or .env to run live CLI e2e tests")


@pytest.fixture
def live_env(tmp_path):
    require_live_e2e()
    env = os.environ.copy()
    env["VAULTS_API_KEY"] = API_KEY or ""
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    return env


def throttle() -> None:
    global LAST_LIVE_CALL
    if RATE_LIMIT_SECONDS <= 0:
        return
    elapsed = time.monotonic() - LAST_LIVE_CALL
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    LAST_LIVE_CALL = time.monotonic()


def run_cli_json(args: list[str], env: dict[str, str], timeout: int = 90) -> Any:
    throttle()
    result = subprocess.run(
        [sys.executable, "-m", "agent.cli.main", "-o", "json", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert not (isinstance(payload, dict) and payload.get("error")), payload
    return payload


def extract_json_values(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    while index < len(text):
        if text[index] not in "{[":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        values.append(value)
        index += end
    return values


def assert_paginated(payload: Any) -> None:
    assert isinstance(payload, dict)
    assert isinstance(payload.get("itemsOnPage"), int)
    assert isinstance(payload.get("data"), list)


def assert_list(payload: Any) -> None:
    assert isinstance(payload, list)


def assert_dict(payload: Any) -> None:
    assert isinstance(payload, dict)


def assert_no_api_error(payload: Any) -> None:
    assert not (isinstance(payload, dict) and payload.get("error")), payload


def assert_networks(payload: Any) -> None:
    assert_list(payload)
    assert any(item.get("name") == "base" for item in payload if isinstance(item, dict))


def assert_health(payload: Any) -> None:
    assert isinstance(payload, dict)
    assert payload.get("status")
    assert payload.get("message")


def test_live_shell_smoke_commands_return_api_json(live_env):
    commands = [
        "-o json api health",
        "-o json api networks",
        "-o json api vaults list --network base --asset-symbol USDC --per-page 1",
    ]
    process = subprocess.Popen(
        [sys.executable, "-m", "agent.cli.main", "shell"],
        cwd=ROOT,
        env=live_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    for command in commands:
        throttle()
        process.stdin.write(f"{command}\n")
        process.stdin.flush()
    process.stdin.write("exit\n")
    process.stdin.flush()
    stdout, stderr = process.communicate(timeout=90)

    assert process.returncode == 0, stdout + stderr
    values = extract_json_values(stdout)
    assert len(values) == 3, stdout
    for value in values:
        assert_no_api_error(value)
    assert_health(values[0])
    assert_networks(values[1])
    assert_paginated(values[2])


def live_seed(env: dict[str, str]) -> dict[str, str]:
    vaults = run_cli_json(
        ["api", "vaults", "list", "--network", "base", "--asset-symbol", "USDC", "--only-transactional", "--per-page", "1"],
        env,
    )
    assert_paginated(vaults)
    if not vaults["data"]:
        pytest.skip("live API returned no transactional Base USDC vaults to seed endpoint tests")
    vault = vaults["data"][0]
    asset = vault.get("asset") or {}
    return {
        "network": vault.get("network", {}).get("name") or "base",
        "vault_id": vault["vaultId"],
        "asset_address": asset["address"],
        "user_address": USER_ADDRESS,
    }


def test_live_full_no_funds_api_command_surface(live_env):
    require_live_e2e(full=True)
    seed = live_seed(live_env)
    network = seed["network"]
    vault_id = seed["vault_id"]
    asset_address = seed["asset_address"]
    user_address = seed["user_address"]

    cases = [
        (["api", "health"], assert_health),
        (["api", "networks"], assert_networks),
        (["api", "tags"], assert_list),
        (["api", "curators"], assert_list),
        (["api", "protocols"], assert_list),
        (["api", "vaults", "list", "--network", network, "--asset-symbol", "USDC", "--per-page", "2"], assert_paginated),
        (["api", "assets", "list", "--network", network, "--per-page", "2"], assert_paginated),
        (["api", "detailed-vaults", "list", "--allowed-network", network, "--allowed-asset", "USDC", "--per-page", "2"], assert_paginated),
        (["api", "detailed-vaults", "get", network, vault_id], assert_dict),
        (["api", "detailed-vaults", "apy", network, vault_id], assert_dict),
        (["api", "detailed-vaults", "tvl", network, vault_id], assert_dict),
        (["api", "historical", "vault", network, vault_id, "--per-page", "2"], assert_paginated),
        (["api", "historical", "apy", network, vault_id, "--per-page", "2"], assert_paginated),
        (["api", "historical", "tvl", network, vault_id, "--per-page", "2"], assert_paginated),
        (["api", "historical", "share-price", network, vault_id, "--per-page", "2"], assert_paginated),
        (["api", "historical", "asset-prices", network, asset_address, "--per-page", "2"], assert_paginated),
        (["api", "portfolio", "best-vault", user_address, "--allowed-network", network, "--allowed-asset", "USDC"], assert_dict),
        (["api", "portfolio", "positions", user_address, "--allowed-network", network, "--allowed-asset", "USDC"], assert_paginated),
        (["api", "portfolio", "best-deposit-options", user_address, "--allowed-network", network, "--allowed-asset", "USDC"], assert_dict),
        (["api", "portfolio", "idle-assets", user_address, "--allowed-network", network, "--allowed-asset", "USDC"], assert_paginated),
        (["api", "transactions", "context", user_address, network, vault_id], assert_dict),
        (["api", "transactions", "suffix", user_address, vault_id], assert_dict),
        (["api", "transactions", "payload", "deposit", user_address, network, vault_id, "--asset-address", asset_address, "--amount", "1"], assert_dict),
        (["api", "transactions", "rewards", "context", user_address], assert_dict),
        (["api", "benchmarks", "get", network, "--code", "usd"], assert_dict),
        (["api", "benchmarks", "history", network, "--code", "usd", "--per-page", "2"], assert_paginated),
        (["api", "nrt", "vault", network, vault_id], assert_dict),
        (["api", "nrt", "share-price", network, vault_id], assert_dict),
        (["api", "nrt", "total-supply", network, vault_id], assert_dict),
        (["api", "nrt", "total-assets", network, vault_id], assert_dict),
        (["api", "nrt", "underlying-asset-price", network, vault_id], assert_dict),
        (["api", "request", "/v2/networks"], assert_networks),
    ]

    for args, assertion in cases:
        assertion(run_cli_json(args, live_env))

    rewards = run_cli_json(["api", "transactions", "rewards", "context", user_address], live_env)
    claim_ids = [
        reward.get("claimId")
        for rewards_by_network in (rewards.get("claimable") or {}).values()
        for reward in rewards_by_network
        if isinstance(reward, dict) and reward.get("claimId")
    ]
    if claim_ids:
        assert_dict(run_cli_json(["api", "transactions", "rewards", "claim", user_address, "--claim-id", claim_ids[0]], live_env))
