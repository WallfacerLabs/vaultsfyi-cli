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

Only after explicit permission unless an external policy grants live execution:

```bash
vaultsfyi --agent conservative execute-decision decision.json --packet packet.json --yes
```

## Recommended OpenClaw agents

- **Yield scout**: read-only, generates packets and reports opportunities.
- **Allocator**: reads packets, emits decision JSON, no execution.
- **Risk reviewer**: reviews packet + decision, flags issues.
- **Operator**: validates/plans/executes after user approval.

All agents should use the CLI as the boundary. They should not build raw txs, hold private keys, or call OWS directly.

## Safety expectations

OpenClaw may run freely:

```bash
vaultsfyi status
vaultsfyi opportunities --preference blue-chip
vaultsfyi decision-packet --preference blue-chip -o json
vaultsfyi validate-decision decision.json --packet packet.json -o json
vaultsfyi plan-decision decision.json --packet packet.json -o json
```

OpenClaw should require approval for:

```bash
vaultsfyi execute-decision decision.json --packet packet.json --yes
vaultsfyi deploy --percent 10 --yes
vaultsfyi redeem --position NAME --yes
```
