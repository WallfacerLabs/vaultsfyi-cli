# vaultsfyi-cli

Command-line DeFi vault management powered by [vaults.fyi](https://vaults.fyi). Browse idle USDC, inspect positions, find yield opportunities, and deploy/redeem capital from a terminal, scripts, agents, or Python.

The CLI binary is `vaultsfyi`.

## What it does

- Checks wallet gas, idle USDC, and vault positions on Base
- Finds filtered USDC deposit opportunities through vaults.fyi
- Selects the highest-yield eligible vault while avoiding existing positions
- Generates and broadcasts approve/deposit and redeem transactions
- Supports human table output and machine-readable JSON
- Provides an interactive command shell
- Keeps the Python API available: `from agent import Agent`

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

If the GitHub repo has not been renamed yet, clone the current repo/branch and run the same install command.

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
vaultsfyi deploy --percent 10       # deploy 10% of idle USDC
vaultsfyi redeem --position NAME    # redeem a position by nickname
vaultsfyi redeem-all                # redeem all active positions
vaultsfyi shell                     # interactive command shell

vaultsfyi wallet create
vaultsfyi wallet show
vaultsfyi wallet address

vaultsfyi config path
vaultsfyi config show
vaultsfyi config set vaults.api_key YOUR_KEY
```

Global flags:

```bash
vaultsfyi --output table positions
vaultsfyi -o json positions
vaultsfyi --config ~/.config/vaultsfyi/config.toml status
```

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

[strategy]
network = "base"
asset = "USDC"
asset_address = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
min_deposit_usd = 0.10
min_apy = 0.01
min_tvl = 1000000
apy_interval = "1day"
only_transactional = true
vault_whitelist = []

[display]
decimals = 2
position_retry_attempts = 3
position_retry_delay = 5
```

Precedence:

```text
CLI flags > environment variables > user config > legacy project config fallback > defaults
```

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
- `--dry-run` never broadcasts
- Gas is checked before transaction generation/execution
- Failed deposit flows do not revoke approvals automatically

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
