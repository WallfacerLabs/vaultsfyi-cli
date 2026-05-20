# Multi-agent profiles

Multi-agent support is optional. Single-wallet users can ignore this entire page.

A named agent profile is a config overlay with its own wallet, strategy, preferences, risk limits, and execution defaults.

## Create profiles

```bash
vaultsfyi agent init conservative --wallet ows-conservative --mode dry-run
vaultsfyi agent init high-yield --wallet ows-high-yield --mode dry-run
vaultsfyi agent list
```

Profiles live at:

```text
~/.config/vaultsfyi/agents/<name>.toml
```

## Create profile wallets

```bash
vaultsfyi --agent conservative wallet create
vaultsfyi --agent high-yield wallet create
vaultsfyi --agent conservative wallet address
vaultsfyi --agent high-yield wallet address
```

Fund each wallet separately. Avoid sharing one wallet across multiple live agents unless you have a very good reason.

## Run ordinary commands through a profile

```bash
vaultsfyi --agent conservative status
vaultsfyi --agent conservative positions
vaultsfyi --agent conservative opportunities
vaultsfyi --agent conservative deploy --percent 10
```

## Tune a profile

```bash
vaultsfyi --agent conservative config set strategy.min_apy 0.03
vaultsfyi --agent conservative config set strategy.max_apy 0.15
vaultsfyi --agent conservative config set strategy.min_tvl 10000000
vaultsfyi --agent conservative config set agent.max_deploy_usd 100
```

`config set` with `--agent` writes to that profile, not the global config.

## Compare profiles

```bash
vaultsfyi agent compare conservative high-yield
```

## Agent run

```bash
vaultsfyi agent run conservative --dry-run
```

`agent run` performs one strategy pass and emits a dry-run plan when possible.

Live execution is explicit:

```bash
vaultsfyi --agent conservative config set agent.mode live
vaultsfyi agent run conservative --execute --yes
```

This is the preferred autonomous-management entrypoint. An OpenClaw host or
scheduler may run it without per-run approval only after the specific named
profile has been approved for unattended live operation. Direct one-off
broadcast commands such as `deploy --yes`, `redeem --yes`, and
`execute-decision --yes` should still require human approval in OpenClaw
contexts.

## Wallet locks

Live transaction commands acquire a per-wallet lock:

```text
~/.local/state/vaultsfyi/locks/<wallet>.lock
```

This prevents two processes from broadcasting from the same OWS wallet at the same time.
