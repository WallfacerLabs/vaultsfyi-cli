# vaultsfyi-cli

Command-line DeFi vault management powered by [vaults.fyi](https://vaults.fyi). Browse idle USDC, inspect positions, find yield opportunities, and deploy/redeem capital from a terminal, scripts, agents, or Python.

The CLI binary is `vaultsfyi`.

## What it does

- Checks wallet gas, idle USDC, and vault positions on Base
- Finds filtered USDC deposit opportunities through vaults.fyi
- Selects the highest-yield eligible vault while avoiding existing positions
- Supports reusable preference filters for vault eligibility
- Emits decision packets for OpenClaw or another external allocator
- Validates allocator decisions before planning or execution
- Generates and broadcasts approve/deposit/redeem transactions through OWS
- Supports human table output and machine-readable JSON
- Provides an interactive command shell
- Keeps the Python API available: `from agent import Agent`

## Documentation

- [Single-agent / single-wallet usage](docs/single-agent.md)
- [Human operator workflows](docs/human-usage.md)
- [Multi-agent profiles](docs/multi-agent.md)
- [Preferences and hard filters](docs/preferences.md)
- [Decision packet and validation model](docs/decisions.md)
- [OpenClaw allocator workflow](docs/openclaw.md)
- [Command reference](docs/commands.md)
- [Safety model](docs/safety.md)

## Wallet model

`vaultsfyi` uses [Open Wallet Standard](https://openwallet.sh/) for wallet storage and signing.

- No repo-specific plaintext `PRIVATE_KEY` file
- OWS wallet data lives locally, normally under `~/.ows/`
- The agent/CLI sees the wallet name and public address
- Transactions are signed through OWS and broadcast locally
- Paid x402 API requests can be handled through `ows pay request`

## Install

```bash
git clone https://github.com/WallfacerLabs/vaultsfyi-cli.git
cd vaultsfyi-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

Install the OWS CLI if you want x402-paid requests without a vaults.fyi API key:

```bash
curl -fsSL https://docs.openwallet.sh/install.sh | bash
ows wallet info
```

## Quick start

```bash
vaultsfyi setup --wallet agent-treasury
vaultsfyi wallet create --name agent-treasury
vaultsfyi wallet address
```

Fund the printed Base address with:

- ETH for gas, e.g. `0.002 ETH`
- USDC for deposits and/or x402 payments, e.g. `10 USDC`

Then run:

```bash
vaultsfyi status
vaultsfyi idle
vaultsfyi positions
vaultsfyi opportunities --limit 10
```

Transactional commands ask before broadcasting:

```bash
vaultsfyi deploy --percent 10
vaultsfyi redeem --position YearnUSDCV --percent 50
vaultsfyi redeem-all
```

For automation, confirmation must be explicit:

```bash
vaultsfyi -o json deploy --percent 10 --yes
vaultsfyi -o json redeem --position YearnUSDCV --percent 50 --yes
```

Use `--dry-run` to build a transaction plan without broadcasting:

```bash
vaultsfyi deploy --percent 10 --dry-run
vaultsfyi -o json redeem --position YearnUSDCV --percent 50 --dry-run
```

## Commands

```bash
vaultsfyi status                    # wallet, gas, idle USDC, position count
vaultsfyi idle                      # idle USDC only
vaultsfyi positions                 # active positions
vaultsfyi opportunities             # deposit opportunities
vaultsfyi opportunities --preference blue-chip
vaultsfyi deploy --percent 10       # deploy 10% of idle USDC
vaultsfyi deploy --percent 10 --preference blue-chip
vaultsfyi redeem --position NAME    # redeem a position by nickname
vaultsfyi redeem-all                # redeem all active positions
vaultsfyi shell                     # interactive command shell

vaultsfyi wallet create
vaultsfyi wallet show
vaultsfyi wallet address

vaultsfyi config path
vaultsfyi config show
vaultsfyi config set vaults.api_key YOUR_KEY

vaultsfyi preference init blue-chip
vaultsfyi preference list
vaultsfyi preference set blue-chip min_tvl 10000000

vaultsfyi decision-packet --preference blue-chip -o json
vaultsfyi validate-decision decision.json --packet packet.json
vaultsfyi plan-decision decision.json --packet packet.json
vaultsfyi execute-decision decision.json --packet packet.json --yes
```

Global flags:

```bash
vaultsfyi --output table positions
vaultsfyi -o json positions
vaultsfyi --config ~/.config/vaultsfyi/config.toml status
```

`--agent NAME` is optional and only needed when you deliberately use named multi-agent profiles.

## Interactive shell

```bash
vaultsfyi shell
```

Inside the shell:

```text
vaultsfyi> status
vaultsfyi> idle
vaultsfyi> positions
vaultsfyi> opportunities --limit 5
vaultsfyi> deploy --percent 10
vaultsfyi> redeem --position YearnUSDCV --percent 50
vaultsfyi> exit
```

## Configuration

Primary config lives at:

```text
~/.config/vaultsfyi/config.toml
```

Example:

```toml
[wallet]
name = "agent-treasury"
chain = "base"
# vault_path = "~/.ows"
# ows_cli_path = "/usr/local/bin/ows"

[network]
rpc_url = "https://mainnet.base.org"

[vaults]
api_url = "https://api.vaults.fyi"
# api_key = "..."

[agent]
name = "default"
mode = "dry-run" # dry-run | paper | live
# max_deploy_usd = 100
# max_position_pct = 25 # cap deploy/rebalance target size as a percent of portfolio value

[strategy]
network = "base"
asset = "USDC"
asset_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
min_deposit_usd = 0.10
min_apy = 0.01
# max_apy = 0.25
min_tvl = 1000000
# max_tvl = 50000000
apy_interval = "1day" # preferred when API returns interval-specific APY; total APY fallback
only_transactional = true
# only_app_featured = true
allow_corrupted = false
# allow_vaults_with_warnings = false
# min_vault_score = 8
allowed_assets = [] # defaults to [asset] when empty
disallowed_assets = []
allowed_networks = [] # defaults to [network] when empty
disallowed_networks = []
tags = []
curators = []
# sort_by = "apy7day" # tvl | apy1day | apy7day | apy30day
# sort_order = "desc" # asc | desc
vault_whitelist = []
allowed_protocols = []
disallowed_protocols = []
blocked_protocols = [] # legacy alias for disallowed_protocols
allowed_curators = [] # legacy alias for curators

[risk]
# max_single_vault_usd = 100
require_withdrawable = false # when true, vaults without withdrawability data are excluded
# min_vault_age_days = 14 # when set, vaults without age data are excluded
allow_incentive_heavy_yield = true # when false, reward-heavy APY is excluded when API exposes APY components

[execution]
deploy_percent = 10.0
require_confirmation = true
slippage_bps = 50 # reserved for transaction endpoint support
cooldown_after_tx = "10m" # advisory for external schedulers

[decision]
min_net_gain_usd = 1.0
max_breakeven_days = 30
min_apy_improvement = 0.01
max_rebalance_pct = 50
allow_partial_rebalance = true
prefer_hold_if_uncertain = true
eth_usd_price = 3000.0
deposit_gas_units = 350000
redeem_gas_units = 500000

[preferences.blue-chip]
min_tvl = 10000000
min_apy = 0.02
max_apy = 0.15
only_transactional = true
allowed_assets = ["USDC"]
allowed_networks = ["base", "mainnet"]
tags = ["stablecoin"]
curators = []
allowed_protocols = ["aave", "morpho", "euler"]
disallowed_protocols = []
vault_whitelist = []

[display]
decimals = 2
position_retry_attempts = 3
position_retry_delay = 5
```

Config resolution, from lowest to highest priority:

```text
1. built-in defaults
2. global config: ~/.config/vaultsfyi/config.toml
3. selected agent profile: ~/.config/vaultsfyi/agents/<agent>.toml
4. supported environment variables
5. selected preference copied into strategy for that command
6. explicit command flags
```

Later layers override earlier layers for the same key. Preferences are per-command overlays selected with `--preference`; they do not rewrite the config file.

Supported environment overrides:

```bash
OWS_WALLET=agent-treasury
OWS_CHAIN=base
OWS_VAULT_PATH=/path/to/ows-vault
OWS_CLI_PATH=/usr/local/bin/ows
BASE_RPC_URL=https://mainnet.base.org
VAULTS_API_KEY=...
VAULTS_API_URL=https://api.vaults.fyi
```

## Python API still works

The CLI is the main product surface, but direct Python usage remains supported.

```python
from agent import Agent

agent = Agent()
agent.show_state()
agent.show_idle_assets()
agent.deploy_capital(10)
agent.show_positions()
agent.redeem('YearnUSDCV', 50)
agent.redeem_all()
```

For structured use:

```python
state = agent.get_state()
positions = agent.get_positions()
opportunities = agent.get_opportunities()
plan = agent.prepare_deploy(10)
```

## Output contract

Table mode is for humans:

```bash
vaultsfyi positions
```

JSON mode is for scripts and agents:

```bash
vaultsfyi -o json positions
```

Errors in JSON mode are emitted as:

```json
{ "error": "..." }
```

and the process exits non-zero.

## Transaction safety

- `deploy`, `redeem`, and `redeem-all` ask for confirmation by default
- JSON mode still requires `--yes` to broadcast
- In OpenClaw contexts, direct broadcast commands with `--yes` should still require host-level approval
- `--dry-run` never broadcasts
- Gas is checked before transaction generation/execution
- Failed deposit flows do not revoke approvals automatically

## Optional: multiple wallets and strategy agents

Single-wallet usage does not require any of this. Use named profiles only when you want several isolated strategies or wallets.

A profile is a separate strategy config that points at its own OWS wallet:

```bash
vaultsfyi agent init conservative --wallet ows-conservative --mode dry-run
vaultsfyi agent init high-yield --wallet ows-high-yield --mode dry-run
vaultsfyi agent list
```

Run ordinary commands through a profile with `--agent`:

```bash
vaultsfyi --agent conservative wallet create
vaultsfyi --agent conservative wallet address
vaultsfyi --agent conservative opportunities
```

Tune a profile without changing the global config:

```bash
vaultsfyi --agent conservative config set strategy.min_apy 0.03
vaultsfyi --agent conservative config set strategy.max_apy 0.25
vaultsfyi --agent conservative config set agent.max_deploy_usd 100
```

Compare or dry-run strategy passes:

```bash
vaultsfyi agent run conservative --dry-run
vaultsfyi agent compare conservative high-yield
```

Live execution is intentionally explicit:

```bash
vaultsfyi --agent conservative config set agent.mode live
vaultsfyi agent run conservative --execute --yes
```

This is the intended autonomous-management command. Allow it without per-run
approval only for named profiles that have been reviewed for unattended live
operation. Direct one-off commands such as `deploy --yes`, `redeem --yes`, and
`execute-decision --yes` should remain approval-required for OpenClaw.

Live transaction commands take a wallet lock under `~/.local/state/vaultsfyi/locks/` so two processes cannot broadcast from the same OWS wallet at the same time.

Profile files live at:

```text
~/.config/vaultsfyi/agents/<name>.toml
```

Use `vaultsfyi config show --all` or `vaultsfyi agent show NAME` to inspect advanced agent/risk/execution fields.

## Development

```bash
pip install -e '.[test]'
pytest
python -m compileall agent tests
```

## Notes

- Base + USDC focused in the current implementation
- vaults.fyi API key is optional; x402 payments can be used where available
- OWS owns key storage/signing; this repo should not grow private-key management again

## License

MIT
