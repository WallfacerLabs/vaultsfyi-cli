# OpenClaw allocator workflow

OpenClaw should act above `vaultsfyi-cli`, not inside it.

```text
OpenClaw agent = reasoning / allocation / explanation
vaultsfyi-cli = data packet / hard filters / validation / tx planning / OWS execution
```

The CLI does not depend on OpenClaw. OpenClaw does not bypass the CLI.

## Read-only packet

```bash
vaultsfyi --agent conservative decision-packet --preference blue-chip -o json > packet.json
```

OpenClaw reads `packet.json` and chooses one candidate action.

## Prompt shape

Use a prompt like:

```text
You are an allocator. Choose exactly one candidate from this vaultsfyi decision packet.
Optimize net expected yield after gas and churn costs.
Prefer hold when benefit is unclear.
Return only JSON matching vaultsfyi.decision.v1.
Do not invent vault addresses, amounts, or transactions.
```

Expected output:

```json
{
  "schema_version": "vaultsfyi.decision.v1",
  "candidate_id": "hold",
  "action": "hold",
  "confidence": "high",
  "reasoning_summary": "Best candidate has long breakeven; hold is better.",
  "risks": []
}
```

## Validate

```bash
vaultsfyi --agent conservative validate-decision decision.json --packet packet.json -o json
```

If invalid, OpenClaw should stop and report the validation errors.

## Plan

```bash
vaultsfyi --agent conservative plan-decision decision.json --packet packet.json -o json
```

OpenClaw can summarize the plan for a human:

```text
Decision: partial rebalance
From: Aave USDC, 4.2%
To: Euler USDC, 8.1%
Amount: $250
Estimated cost: $0.48
Breakeven: 6 days
Reason: clears blue-chip preference and churn hurdle.
```

## Execute

Only after explicit permission. In an OpenClaw runner, these direct broadcast
commands should be marked as approval-required even when they include `--yes`:

```bash
vaultsfyi --agent conservative execute-decision decision.json --packet packet.json --yes
vaultsfyi --agent conservative deploy --percent 10 --yes
vaultsfyi --agent conservative redeem --position NAME --yes
```

`--yes` only tells `vaultsfyi` not to ask its own interactive prompt. It is not
an OpenClaw approval grant. The OpenClaw host or scheduler should still ask the
human before running direct one-off broadcast commands.

## Recommended OpenClaw agents

- **Yield scout**: read-only, generates packets and reports opportunities.
- **Allocator**: reads packets, emits decision JSON, no execution.
- **Risk reviewer**: reviews packet + decision, flags issues.
- **Operator**: validates/plans/executes after user approval.

All agents should use the CLI as the boundary. They should not build raw txs, hold private keys, or call OWS directly.

## Autonomous management

Use a named agent profile for unattended operation. This is the intended
autonomous path because the policy is bounded by profile config: wallet, mode,
selected preference, deploy percentage, bucket limits, and risk caps.

```bash
vaultsfyi agent init conservative --wallet ows-conservative --mode dry-run
vaultsfyi --agent conservative preference init blue-chip
vaultsfyi --agent conservative preference set blue-chip allowed_assets USDC
vaultsfyi --agent conservative preference set blue-chip allowed_networks base
vaultsfyi --agent conservative preference set blue-chip allowed_protocols aave,morpho,euler
vaultsfyi --agent conservative preference set blue-chip min_tvl 10000000
vaultsfyi --agent conservative preference set blue-chip max_apy 0.15
vaultsfyi --agent conservative preference set blue-chip bucket_max_pct 25
vaultsfyi --agent conservative preference set blue-chip bucket_tolerance_pct 5
vaultsfyi --agent conservative config set agent.preference blue-chip
vaultsfyi --agent conservative config set agent.mode live
vaultsfyi --agent conservative config set agent.max_deploy_usd 100
vaultsfyi --agent conservative config set risk.max_single_vault_usd 100
vaultsfyi --agent conservative config set execution.deploy_percent 10
vaultsfyi agent run conservative --dry-run
```

After the profile has been reviewed and intentionally allowed to operate live,
the autonomous command is:

```bash
vaultsfyi agent run conservative --execute --yes
```

Runner policy recommendation:

- allow read-only OpenClaw commands without approval
- require human approval for direct one-off broadcast commands
- allow `vaultsfyi agent run NAME --execute --yes` without per-run approval only for named profiles that have been explicitly approved for autonomous live operation

The autonomous profile can still be scheduled externally, for example by cron,
a job runner, or an OpenClaw host. The CLI runs one pass at a time and acquires
a wallet lock before broadcasting.

## Safety expectations

OpenClaw may run freely:

```bash
vaultsfyi status
vaultsfyi opportunities --preference blue-chip
vaultsfyi api vaults list --network base --asset-symbol USDC -o json
vaultsfyi decision-packet --preference blue-chip -o json
vaultsfyi validate-decision decision.json --packet packet.json -o json
vaultsfyi plan-decision decision.json --packet packet.json -o json
```

OpenClaw should require approval for:

```bash
vaultsfyi execute-decision decision.json --packet packet.json --yes
vaultsfyi deploy --percent 10 --yes
vaultsfyi redeem --position NAME --yes
vaultsfyi redeem-all --yes
```

`vaultsfyi api ...` commands are chain read-only, including transaction payload
commands that return unsigned payloads. They may still consume vaults.fyi API
credits or use x402 payment handling, so paid API access should be governed by
the host's cost policy.

OpenClaw may run autonomously only through an explicitly approved live profile:

```bash
vaultsfyi agent run NAME --execute --yes
```
