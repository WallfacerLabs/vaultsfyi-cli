# Command reference

## Global options

```bash
vaultsfyi --output table COMMAND
vaultsfyi -o json COMMAND
vaultsfyi --config /path/to/config.toml COMMAND
vaultsfyi --agent conservative COMMAND
```

`--agent` is optional and selects a named profile.

## Core commands

```bash
vaultsfyi setup --wallet agent-treasury
vaultsfyi status
vaultsfyi idle
vaultsfyi positions
vaultsfyi opportunities [--preference NAME] [--limit N]
vaultsfyi deploy --percent 10 [--preference NAME] [--dry-run] [--yes]
vaultsfyi redeem --position NAME --percent 50 [--dry-run] [--yes]
vaultsfyi redeem-all [--dry-run] [--yes]
vaultsfyi shell
```

## Wallet commands

```bash
vaultsfyi wallet create [--name NAME]
vaultsfyi wallet show
vaultsfyi wallet address
```

## Config commands

```bash
vaultsfyi config path
vaultsfyi config show
vaultsfyi config show --all
vaultsfyi config set SECTION.KEY VALUE
```

Examples:

```bash
vaultsfyi config set vaults.api_key YOUR_KEY
vaultsfyi config set strategy.min_apy 0.03
vaultsfyi --agent conservative config set strategy.max_apy 0.15
```

## Agent commands

```bash
vaultsfyi agent init NAME --wallet WALLET --mode dry-run
vaultsfyi agent list
vaultsfyi agent show NAME
vaultsfyi agent run NAME --dry-run
vaultsfyi agent run NAME --execute --yes
vaultsfyi agent compare NAME NAME2
```

## Preference commands

```bash
vaultsfyi preference init NAME
vaultsfyi preference list
vaultsfyi preference show NAME
vaultsfyi preference set NAME KEY VALUE
```

Examples:

```bash
vaultsfyi preference init blue-chip
vaultsfyi preference set blue-chip min_tvl 10000000
vaultsfyi preference set blue-chip allowed_protocols aave,morpho,euler
```

Comma-separated values become lists. `true`, `false`, `null`, integers, and floats are parsed into native TOML values.

## Decision/OpenClaw commands

```bash
vaultsfyi decision-packet [--preference NAME] [--intent TEXT] -o json
vaultsfyi validate-decision decision.json --packet packet.json -o json
vaultsfyi plan-decision decision.json --packet packet.json -o json
vaultsfyi execute-decision decision.json --packet packet.json --yes
```

`decision-packet`, `validate-decision`, and `plan-decision` are read-only with respect to the chain. `execute-decision` signs and broadcasts.
