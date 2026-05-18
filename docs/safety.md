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

The CLI builds all transactions from vaults.fyi transaction endpoints.

## Confirmation

Live transaction commands require confirmation unless `--yes` is explicitly supplied:

```bash
vaultsfyi deploy --percent 10
vaultsfyi execute-decision decision.json --packet packet.json
```

Automation must be explicit:

```bash
vaultsfyi execute-decision decision.json --packet packet.json --yes
```

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
- dry-run commands

Require confirmation:

- `deploy --yes`
- `redeem --yes`
- `redeem-all --yes`
- `execute-decision --yes`

## Known limitations

- Cost estimates use configured gas assumptions and ETH/USD price unless richer data is supplied.
- Withdrawal fees/cooldowns are included only when data is available.
- The decision system is conservative by design. Invalid or marginal decisions should become `hold`.
