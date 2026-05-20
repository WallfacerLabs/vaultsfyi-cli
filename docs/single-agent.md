# Single-agent / single-wallet usage

This is the default path. You do **not** need named agents, preferences, or OpenClaw.

## Setup

```bash
vaultsfyi setup --wallet agent-treasury
vaultsfyi wallet create --name agent-treasury
vaultsfyi wallet address
```

Fund the address on Base with:

- ETH for gas
- USDC for deployment

## Check state

```bash
vaultsfyi status
vaultsfyi idle
vaultsfyi positions
vaultsfyi opportunities
```

## Deploy

```bash
vaultsfyi deploy --percent 10
```

The CLI:

1. checks gas
2. checks idle USDC
3. fetches current positions
4. fetches eligible Base USDC opportunities
5. filters by config
6. excludes vaults already held
7. picks the highest APY remaining vault
8. asks for confirmation
9. signs and broadcasts via OWS

For dry-run:

```bash
vaultsfyi deploy --percent 10 --dry-run
```

For JSON automation:

```bash
vaultsfyi -o json deploy --percent 10 --dry-run
vaultsfyi -o json deploy --percent 10 --yes
```

JSON mode still requires `--yes` for live transactions.

## Redeem

```bash
vaultsfyi positions
vaultsfyi redeem --position YearnUSDCV --percent 50
vaultsfyi redeem-all
```

## Configuration

Default path:

```text
~/.config/vaultsfyi/config.toml
```

Inspect simple config:

```bash
vaultsfyi config show
```

Set values:

```bash
vaultsfyi config set vaults.api_key YOUR_KEY
# or set VAULTS_API_KEY in an ignored .env file
vaultsfyi config set strategy.min_apy 0.03
vaultsfyi config set strategy.min_tvl 5000000
```

Show advanced defaults:

```bash
vaultsfyi config show --all
```
