---
name: openclaw-vaultsfyi-cli
description: Operate vaultsfyi-cli safely from OpenClaw or Codex for DeFi vault allocation workflows. Use when configuring or managing an OpenClaw agent that creates an OWS wallet, defines vault preferences, models max allocation buckets, schedules cron or automation runs, discovers and compares vaults with `vaultsfyi api`, emits/validates/plans decisions, or reports recurring vault actions within user-defined boundaries.
---

# OpenClaw Vaults CLI

## Core Contract

Use `vaultsfyi` as the hard boundary between OpenClaw reasoning and wallet execution.

- Keep private keys in OWS only; do not ask for or store private keys.
- Prefer `-o json` for automation, reports, comparisons, and decision packets.
- Treat preferences, caps, and decision-packet validation as hard boundaries.
- Never build raw transactions outside the CLI.
- Never run live chain-broadcast commands unless the user explicitly approved the exact command or an already-reviewed live agent profile.
- Remember that `vaultsfyi api ...` commands are chain read-only, but may consume API credits or trigger x402 payment handling.

## Workflow

1. **Collect boundaries**: wallet/profile name, allowed assets/networks/protocols, min TVL/APY/score, warning/corruption policy, bucket sizes, schedule, reporting channel, and whether execution is dry-run or approved live.
2. **Create wallet/profile**: use an OWS wallet through `vaultsfyi wallet create`; start agent profiles in `dry-run`.
3. **Define preferences**: create reusable `vaultsfyi preference` filters for each allowed risk sleeve.
4. **Model allocation buckets**: represent each bucket as a named agent profile plus a selected `agent.preference` and caps. Put bucket max/tolerance on the preference; use `agent.max_deploy_usd`, `agent.max_position_pct`, `risk.max_single_vault_usd`, `execution.deploy_percent`, and `[decision]` thresholds for remaining limits. Do not invent unsupported bucket config keys.
5. **Discover and compare**: use `vaultsfyi api` for broad market discovery and `vaultsfyi opportunities`, `decision-packet`, `validate-decision`, and `plan-decision` for bounded decisions.
6. **Schedule/report**: for cron or automation, default to read-only scouting and dry-runs. Send the user a summary every run, including no-op runs and failures.

For exact commands and report templates, read [CLI Playbook](references/cli-playbook.md).

## Decision Rules

Use the decision-packet flow for allocator choices:

1. Run `vaultsfyi --agent NAME decision-packet --preference PREF -o json`.
2. Choose exactly one candidate from the packet, or choose `hold`.
3. Return only `vaultsfyi.decision.v1` JSON.
4. Run `validate-decision`; stop on validation errors.
5. Run `plan-decision`; summarize unsigned plan details.
6. Run `execute-decision --yes` only after approval, unless the user has explicitly approved `vaultsfyi agent run NAME --execute --yes` for that live profile.

Prefer `hold` when the opportunity is marginal, data is missing, costs exceed thresholds, warnings conflict with user policy, or the action would exceed a bucket cap.

## Cron And Updates

When a user asks for recurring monitoring, reminders, cron actions, scheduled OpenClaw runs, or ongoing updates:

- Use the platform automation tool when available.
- Prefer read-only scheduled prompts unless the user has explicitly approved a live profile.
- Include the workspace path and exact command set in the automation prompt.
- Report every run with: timestamp, profile/bucket, commands run, current idle/positions, top candidates, proposed decision or hold reason, validation/plan result, errors, and next run.
- Escalate to the user instead of executing when a run would require a new wallet, new allowance, new protocol outside preferences, depleted gas, API payment approval, or a live broadcast not already approved.

## Safety Checklist

Before live operation, verify:

- Wallet address was shown to the user and funded intentionally.
- `vaultsfyi status`, `idle`, and `positions` work for the profile.
- `vaultsfyi preference show PREF` matches the user's stated boundaries.
- `vaultsfyi --agent NAME config show --all` shows `agent.preference = "PREF"` and reviewed caps.
- `vaultsfyi agent run NAME --dry-run` succeeds.
- The user approved either a single live command or the exact profile/schedule allowed to run unattended.
