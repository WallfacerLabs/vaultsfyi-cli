# Human operator workflows

Use this when a human is directly operating the CLI.

## Normal loop

```bash
vaultsfyi status
vaultsfyi positions
vaultsfyi opportunities
vaultsfyi deploy --percent 10
```

Read the proposed transaction summary. Confirm only if it matches your intent.

## Safer deploy workflow

```bash
vaultsfyi deploy --percent 10 --dry-run
vaultsfyi deploy --percent 10
```

Dry-run builds the plan without broadcasting.

## Preference-filtered human deploy

```bash
vaultsfyi preference init blue-chip
vaultsfyi preference set blue-chip min_tvl 10000000
vaultsfyi preference set blue-chip max_apy 0.15
vaultsfyi opportunities --preference blue-chip
vaultsfyi deploy --percent 10 --preference blue-chip
```

Preferences are hard filters. The CLI will not deploy into vaults outside the selected preference.

## Human + OpenClaw assist

A human can ask OpenClaw to analyze a packet but keep final execution manual:

```bash
vaultsfyi decision-packet --preference blue-chip -o json > packet.json
```

OpenClaw reads `packet.json`, emits a `decision.json`, then the human runs:

```bash
vaultsfyi validate-decision decision.json --packet packet.json
vaultsfyi plan-decision decision.json --packet packet.json
vaultsfyi execute-decision decision.json --packet packet.json
```

`execute-decision` still asks for confirmation unless `--yes` is provided.

## Things humans should check

- target vault name/address
- amount
- estimated cost and breakeven days
- whether the decision is `hold`, `deploy_idle`, `rebalance`, or `partial_rebalance`
- whether preference filters match the intended risk posture

If the explanation is vague, do not execute. The chain does not care that the vibes were immaculate.
