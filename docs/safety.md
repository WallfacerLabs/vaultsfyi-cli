# Safety model

## Custody

`vaultsfyi` uses Open Wallet Standard for key storage and signing.

- no repo-specific plaintext private key
- no LLM receives private keys
- no OpenClaw agent signs directly
- signing happens through OWS from deterministic CLI transaction plans

## Hard boundaries

Preferences are hard eligibility filters. Decisions outside the selected preference are invalid.

The validator rejects:

- unknown candidate IDs
- targets outside eligible vaults
- sources outside current positions
- invalid amounts
- target vault allocation caps
- breakeven above policy
- net gain below policy
- malformed schema

## Transaction boundary

External allocators only choose candidate IDs.

They cannot provide:

- arbitrary transaction data
- arbitrary target addresses
- arbitrary spender addresses
- arbitrary call data

The CLI builds all transactions from vaults.fyi transaction endpoints. If an
endpoint returns no usable transaction actions, the CLI fails closed instead of
constructing fallback call data.

Full redeem planning leaves the configured `execution.redeem_dust_usd`
threshold, default `$0.01`, instead of trying to drain exact dust balances.

## Confirmation

Live transaction commands require confirmation unless `--yes` is explicitly supplied:

```bash
vaultsfyi deploy --percent 10
vaultsfyi execute-decision decision.json --packet packet.json
```

`--yes` bypasses the CLI's interactive prompt. It does not mean an external
allocator, such as OpenClaw, has permission to run the command without host
approval.

For OpenClaw or another external runner, these direct one-off broadcast commands
should require human approval even with `--yes`:

```bash
vaultsfyi execute-decision decision.json --packet packet.json --yes
vaultsfyi deploy --percent 10 --yes
vaultsfyi redeem --position NAME --yes
vaultsfyi redeem-all --yes
```

Unattended operation should use a named live agent profile instead:

```bash
vaultsfyi agent run NAME --execute --yes
```

Only allow that autonomous command after the named profile's wallet, selected
preference, bucket limits, deploy size, and risk caps have been reviewed.

## Wallet locks

Live execution acquires a lock per OWS wallet:

```text
~/.local/state/vaultsfyi/locks/<wallet>.lock
```

This prevents same-wallet race conditions.

## OpenClaw policy recommendation

Allowed without confirmation:

- `status`
- `idle`
- `positions`
- `opportunities`
- `decision-packet`
- `validate-decision`
- `plan-decision`
- `api ...` commands that only read data or generate unsigned transaction payloads
- dry-run commands

Require confirmation:

- `deploy --yes`
- `redeem --yes`
- `redeem-all --yes`
- `execute-decision --yes`

Autonomous exception:

- `agent run NAME --execute --yes`, but only for a named profile that has been explicitly approved for unattended live operation

`api ...` commands do not sign or broadcast chain transactions. They can still
consume vaults.fyi API credits or trigger x402 payment handling when no API key
is configured, so hosts that require approval for paid network calls should
enforce that separately from chain-broadcast approval.

## Known limitations

- Cost estimates use configured gas assumptions and ETH/USD price unless richer data is supplied.
- Withdrawability, vault age, and incentive-heavy APY filters depend on vaults.fyi response fields; explicit filters fail closed when required data is absent.
- Withdrawal fees and protocol cooldowns are not yet modeled in decision costs
  unless future vault data or transaction endpoint support exposes them.
- `slippage_bps` and `cooldown_after_tx` are configuration placeholders for transaction endpoint support and external scheduler policy.
- The decision system is conservative by design. Invalid or marginal decisions should become `hold`.
