# Decision packets and validation

The decision system lets an external allocator, such as OpenClaw, reason about portfolio actions without receiving signing power.

The CLI owns:

- wallet/config loading
- preference filtering
- candidate generation
- cost estimates
- validation
- transaction planning
- OWS signing and broadcasting

The external allocator owns:

- reasoning over the packet
- choosing one candidate action
- explaining the decision

## Packet

Create a packet:

```bash
vaultsfyi decision-packet --preference blue-chip -o json > packet.json
```

Schema:

```json
{
  "schema_version": "vaultsfyi.decision-packet.v1",
  "wallet": "0x...",
  "agent": "default",
  "preference": "blue-chip",
  "intent": "optimize net yield without excessive churn",
  "idle_assets": {},
  "current_positions": [],
  "eligible_vaults": [],
  "candidate_actions": [],
  "constraints": {}
}
```

## Candidate actions

The CLI emits legal candidate actions:

```json
{ "id": "hold", "type": "hold" }
```

```json
{
  "id": "deploy_idle:0xvault:100.000000",
  "type": "deploy_idle",
  "target_vault_address": "0xvault",
  "amount_usd": 100,
  "target_apy": 0.07,
  "breakeven_days": 4.2
}
```

```json
{
  "id": "partial_rebalance:0xold:0xnew:250.000000",
  "type": "partial_rebalance",
  "source_vault_address": "0xold",
  "target_vault_address": "0xnew",
  "amount_usd": 250,
  "apy_delta": 0.035,
  "breakeven_days": 12
}
```

The allocator must choose one `candidate_id`. It may not invent an action, address, amount, or transaction.

## Decision object

```json
{
  "schema_version": "vaultsfyi.decision.v1",
  "candidate_id": "partial_rebalance:0xold:0xnew:250.000000",
  "action": "partial_rebalance",
  "confidence": "medium",
  "reasoning_summary": "Yield improvement clears the churn hurdle; partial move limits exposure.",
  "risks": ["APY includes incentives"]
}
```

For hold:

```json
{
  "schema_version": "vaultsfyi.decision.v1",
  "candidate_id": "hold",
  "action": "hold",
  "confidence": "high",
  "reasoning_summary": "Best rebalance has 93-day breakeven, not worth churn.",
  "risks": []
}
```

## Validate

```bash
vaultsfyi validate-decision decision.json --packet packet.json -o json
```

Validator checks:

- packet schema
- decision schema
- candidate exists
- target vault is eligible
- source position exists
- amount is valid
- breakeven is within configured policy
- expected net gain clears configured policy

Invalid decisions cannot be planned or executed.

## Plan

```bash
vaultsfyi plan-decision decision.json --packet packet.json -o json
```

This builds unsigned transaction payloads. It does not sign or broadcast.

## Execute

```bash
vaultsfyi execute-decision decision.json --packet packet.json --yes
```

Execution validates again, builds the plan again, acquires the wallet lock, signs through OWS, and broadcasts.

For OpenClaw or another external runner, this direct broadcast command should
require human approval even with `--yes`. `--yes` only bypasses the CLI's own
interactive prompt. Unattended live operation should use an explicitly approved
named profile:

```bash
vaultsfyi agent run NAME --execute --yes
```

## Decision config

```toml
[decision]
min_net_gain_usd = 1.00
max_breakeven_days = 30
min_apy_improvement = 0.01
max_rebalance_pct = 50
allow_partial_rebalance = true
prefer_hold_if_uncertain = true
eth_usd_price = 3000.0
deposit_gas_units = 350000
redeem_gas_units = 500000
```

Cost estimates are conservative approximations until richer vault/protocol fee data is available.
