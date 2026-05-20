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

## Low-level API commands

The `api` namespace maps directly to the Vaults.fyi V2 API. Use `-o json` to
return the exact API response for scripts; table output is a compact human
summary. List filters accept repeated flags or comma-separated values.

```bash
vaultsfyi api health
vaultsfyi api request /v2/vaults -q network=base -q assetSymbol=USDC
```

General/reference endpoints:

```bash
vaultsfyi api vaults list [--page N] [--per-page N] [--network NAME_OR_CAIP] [--asset-symbol SYMBOL]
vaultsfyi api assets list [--page N] [--per-page N] [--network NAME_OR_CAIP]
vaultsfyi api tags
vaultsfyi api networks
vaultsfyi api curators
vaultsfyi api protocols
```

Detailed vault endpoints:

```bash
vaultsfyi api detailed-vaults list [--allowed-asset USDC] [--allowed-network base] [--min-tvl 1000000] [--sort-by tvl]
vaultsfyi api detailed-vaults get NETWORK VAULT_ID
vaultsfyi api detailed-vaults apy NETWORK VAULT_ID
vaultsfyi api detailed-vaults tvl NETWORK VAULT_ID
```

Historical endpoints:

```bash
vaultsfyi api historical vault NETWORK VAULT_ID [--apy-interval 7day] [--granularity 1day]
vaultsfyi api historical apy NETWORK VAULT_ID
vaultsfyi api historical tvl NETWORK VAULT_ID
vaultsfyi api historical share-price NETWORK VAULT_ID
vaultsfyi api historical asset-prices NETWORK ASSET_ADDRESS
```

Portfolio endpoints:

```bash
vaultsfyi api portfolio best-vault USER_ADDRESS
vaultsfyi api portfolio positions USER_ADDRESS [--sort-by balanceUsd] [--apy-interval 7day]
vaultsfyi api portfolio position USER_ADDRESS NETWORK VAULT_ID
vaultsfyi api portfolio best-deposit-options USER_ADDRESS [--max-vaults-per-asset 3]
vaultsfyi api portfolio idle-assets USER_ADDRESS [--sort-by balanceUsd] [--sort-direction desc]
vaultsfyi api portfolio total-returns USER_ADDRESS NETWORK VAULT_ID
vaultsfyi api portfolio events USER_ADDRESS NETWORK VAULT_ID
```

Transaction endpoints:

```bash
vaultsfyi api transactions context USER_ADDRESS NETWORK VAULT_ID
vaultsfyi api transactions suffix USER_ADDRESS VAULT_ID
vaultsfyi api transactions payload ACTION USER_ADDRESS NETWORK VAULT_ID --asset-address ASSET_ADDRESS [--amount AMOUNT] [--all]
vaultsfyi api transactions rewards context USER_ADDRESS
vaultsfyi api transactions rewards claim USER_ADDRESS --claim-id CLAIM_ID
```

Benchmark and NRT endpoints:

```bash
vaultsfyi api benchmarks get NETWORK --code usd
vaultsfyi api benchmarks history NETWORK --code eth [--page N] [--per-page N]
vaultsfyi api nrt vault NETWORK VAULT_ID
vaultsfyi api nrt share-price NETWORK VAULT_ID
vaultsfyi api nrt total-supply NETWORK VAULT_ID
vaultsfyi api nrt total-assets NETWORK VAULT_ID
vaultsfyi api nrt underlying-asset-price NETWORK VAULT_ID
```

Read-only API transaction commands only return transaction payloads. They do
not sign or broadcast. Use the existing guarded execution commands for live
chain writes.

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

`agent run NAME --execute --yes` is the intended unattended execution command.
Use it only for a named profile that has been deliberately configured for live
operation with reviewed wallet, vault filters, deploy size, and risk caps.

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

When OpenClaw or another external runner is operating the CLI, direct broadcast
commands such as `execute-decision --yes`, `deploy --yes`, `redeem --yes`, and
`redeem-all --yes` should still require host-level human approval. `--yes` only
bypasses the CLI's interactive prompt.
