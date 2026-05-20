# CLI Playbook

Use this reference when configuring OpenClaw to operate `vaultsfyi-cli`.

## Intake

Capture these values before setup:

- Wallet/profile name: e.g. `stable-core`
- Asset and network: high-level execution currently targets Base/USDC
- API payment policy: API key preferred, x402 allowed only if user accepts paid calls
- Risk filters: allowed/disallowed assets, networks, protocols, tags, curators
- Quality filters: min TVL, max APY, min vault score, warning/corruption policy
- Bucket caps: max deploy USD, max position percent, max single-vault USD, deploy percent per run
- Decision constraints: min net gain, max breakeven days, min APY improvement, max rebalance percent
- Schedule: manual, read-only cron, dry-run cron, or approved live profile cron
- Reporting: what summary the user wants after each run

## Wallet And Profile Setup

For a single profile:

```bash
vaultsfyi agent init stable-core --wallet ows-stable-core --mode dry-run
vaultsfyi --agent stable-core wallet create
vaultsfyi --agent stable-core wallet address
vaultsfyi --agent stable-core status
```

Tell the user to fund the printed Base address with ETH for gas and USDC for deposits/x402 payments as needed.

Set API key when available:

```bash
vaultsfyi --agent stable-core config set vaults.api_key YOUR_KEY
```

Inspect the profile:

```bash
vaultsfyi --agent stable-core config show --all
vaultsfyi agent show stable-core
```

## Preferences

Create preferences as hard allowlists/filters:

```bash
vaultsfyi --agent stable-core preference init blue-chip
vaultsfyi --agent stable-core preference set blue-chip allowed_assets USDC
vaultsfyi --agent stable-core preference set blue-chip allowed_networks base
vaultsfyi --agent stable-core preference set blue-chip allowed_protocols aave,morpho,euler
vaultsfyi --agent stable-core preference set blue-chip min_tvl 10000000
vaultsfyi --agent stable-core preference set blue-chip min_apy 0.02
vaultsfyi --agent stable-core preference set blue-chip max_apy 0.15
vaultsfyi --agent stable-core preference set blue-chip min_vault_score 8
vaultsfyi --agent stable-core preference set blue-chip only_transactional true
vaultsfyi --agent stable-core preference set blue-chip allow_corrupted false
vaultsfyi --agent stable-core preference set blue-chip allow_vaults_with_warnings false
vaultsfyi --agent stable-core preference set blue-chip bucket_max_pct 35
vaultsfyi --agent stable-core preference set blue-chip bucket_tolerance_pct 5
vaultsfyi --agent stable-core config set agent.preference blue-chip
vaultsfyi --agent stable-core preference show blue-chip
```

Preference list values may be comma-separated, e.g. `aave,morpho,euler`.

## Allocation Buckets

Model a bucket as a profile plus its selected `agent.preference` plus caps. Use one profile per independent sleeve when buckets need separate wallets, schedules, caps, or risk rules.

Example stable bucket:

```bash
vaultsfyi --agent stable-core config set agent.max_deploy_usd 500
vaultsfyi --agent stable-core config set risk.max_single_vault_usd 250
vaultsfyi --agent stable-core config set execution.deploy_percent 10
vaultsfyi --agent stable-core config set decision.min_net_gain_usd 2
vaultsfyi --agent stable-core config set decision.max_breakeven_days 21
vaultsfyi --agent stable-core config set decision.min_apy_improvement 0.01
vaultsfyi --agent stable-core config set decision.max_rebalance_pct 25
```

Example exploratory bucket:

```bash
vaultsfyi agent init opportunistic --wallet ows-opportunistic --mode dry-run
vaultsfyi --agent opportunistic config set agent.max_deploy_usd 100
vaultsfyi --agent opportunistic config set agent.max_position_pct 10
vaultsfyi --agent opportunistic config set risk.max_single_vault_usd 50
vaultsfyi --agent opportunistic config set execution.deploy_percent 5
vaultsfyi --agent opportunistic preference init opportunistic
vaultsfyi --agent opportunistic preference set opportunistic allowed_assets USDC
vaultsfyi --agent opportunistic preference set opportunistic allowed_networks base
vaultsfyi --agent opportunistic preference set opportunistic min_tvl 1000000
vaultsfyi --agent opportunistic preference set opportunistic max_apy 0.30
vaultsfyi --agent opportunistic preference set opportunistic allow_vaults_with_warnings false
vaultsfyi --agent opportunistic preference set opportunistic bucket_max_pct 10
vaultsfyi --agent opportunistic preference set opportunistic bucket_tolerance_pct 5
vaultsfyi --agent opportunistic config set agent.preference opportunistic
```

Use `vaultsfyi -o json agent compare stable-core opportunistic` to compare buckets.

## Discovery Commands

Start with reference data:

```bash
vaultsfyi --agent stable-core -o json api health
vaultsfyi --agent stable-core -o json api networks
vaultsfyi --agent stable-core -o json api assets list --network base
vaultsfyi --agent stable-core -o json api protocols
vaultsfyi --agent stable-core -o json api tags
vaultsfyi --agent stable-core -o json api curators
```

Search detailed vaults within the user's bounds:

```bash
vaultsfyi --agent stable-core -o json api detailed-vaults list \
  --allowed-asset USDC \
  --allowed-network base \
  --allowed-protocol aave,morpho,euler \
  --min-tvl 10000000 \
  --min-apy 0.02 \
  --max-apy 0.15 \
  --min-vault-score 8 \
  --only-transactional \
  --exclude-corrupted \
  --exclude-vaults-with-warnings \
  --sort-by apy7day \
  --sort-order desc \
  --per-page 25
```

Inspect a candidate:

```bash
vaultsfyi --agent stable-core -o json api detailed-vaults get base VAULT_ID
vaultsfyi --agent stable-core -o json api detailed-vaults apy base VAULT_ID
vaultsfyi --agent stable-core -o json api detailed-vaults tvl base VAULT_ID
vaultsfyi --agent stable-core -o json api historical apy base VAULT_ID --granularity 1day --apy-interval 7day
vaultsfyi --agent stable-core -o json api historical tvl base VAULT_ID --granularity 1day
vaultsfyi --agent stable-core -o json api benchmarks get base --code usd
vaultsfyi --agent stable-core -o json api nrt vault base VAULT_ID
```

Compare on:

- total APY and base-vs-reward composition
- TVL and TVL stability
- vault score and penalty components
- warnings/flags and corruption status
- protocol/product/version and curator
- capacity, fees, and transactional support
- historical APY/TVL trend against benchmark
- whether it fits the active preference and bucket caps

## Portfolio And Opportunity Commands

Use the profile-aware high-level commands for bounded operation:

```bash
vaultsfyi --agent stable-core -o json status
vaultsfyi --agent stable-core -o json idle
vaultsfyi --agent stable-core -o json positions
vaultsfyi --agent stable-core -o json opportunities --preference blue-chip --limit 10
vaultsfyi -o json agent run stable-core --dry-run
```

Use raw portfolio API commands for extra inspection:

```bash
vaultsfyi --agent stable-core -o json api portfolio idle-assets USER_ADDRESS --allowed-network base --allowed-asset USDC
vaultsfyi --agent stable-core -o json api portfolio positions USER_ADDRESS --allowed-network base --allowed-asset USDC --apy-interval 7day
vaultsfyi --agent stable-core -o json api portfolio best-deposit-options USER_ADDRESS --allowed-network base --allowed-asset USDC --min-tvl 10000000 --min-apy 0.02
vaultsfyi --agent stable-core -o json api transactions rewards context USER_ADDRESS
```

## Decision Flow

Generate a packet:

```bash
vaultsfyi --agent stable-core -o json decision-packet --preference blue-chip --intent "Allocate only within the blue-chip bucket." > packet.json
```

Allocator output must be exactly:

```json
{
  "schema_version": "vaultsfyi.decision.v1",
  "candidate_id": "hold",
  "action": "hold",
  "confidence": "high",
  "reasoning_summary": "Hold because no candidate clears the bucket hurdle after costs.",
  "risks": []
}
```

Validate and plan:

```bash
vaultsfyi --agent stable-core -o json validate-decision decision.json --packet packet.json
vaultsfyi --agent stable-core -o json plan-decision decision.json --packet packet.json
```

Execute only with explicit approval:

```bash
vaultsfyi --agent stable-core execute-decision decision.json --packet packet.json --yes
```

For approved autonomous profile runs:

```bash
vaultsfyi --agent stable-core config set agent.mode live
vaultsfyi agent run stable-core --execute --yes
```

## Cron Or Automation Patterns

Read-only scout prompt:

```text
In /path/to/vaults-cli, run read-only vaultsfyi checks for profile stable-core:
status, idle, positions, opportunities --preference blue-chip, and decision-packet.
Do not broadcast. Summarize candidates, validation risks, and whether to hold.
Report even when there is no action.
```

Dry-run allocator prompt:

```text
In /path/to/vaults-cli, run vaultsfyi agent run stable-core --dry-run using the
profile's configured agent.preference. Do not broadcast. Report the
current allocation, proposed plan, blocked actions, errors, and next scheduled run.
```

Approved live profile prompt:

```text
In /path/to/vaults-cli, run vaultsfyi agent run stable-core --execute --yes only
for the already-approved stable-core live profile. Do not run direct deploy,
redeem, redeem-all, or execute-decision commands. Report command output,
transaction hashes if any, no-op reasons, errors, and next scheduled run.
```

Every report should include:

- run time and schedule
- profile and bucket
- commands executed
- wallet address, gas status, idle balance, active positions
- top candidates and why they passed/failed
- selected decision or hold reason
- plan summary and transaction hashes when applicable
- any API/x402 payment issue or chain execution issue
- next action required from the user
