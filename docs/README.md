# vaultsfyi-cli documentation

`vaultsfyi` can be used in five modes:

1. **Human single-wallet CLI**: one wallet, direct commands, simplest path.
2. **Named agent profiles**: multiple wallets/strategies, still deterministic CLI execution.
3. **Preference-filtered execution**: reusable hard boundaries for vault eligibility.
4. **OpenClaw allocator workflow**: OpenClaw reasons over a decision packet, then the CLI validates/plans/executes.
5. **Low-level Vaults.fyi API access**: direct V2 API commands under `vaultsfyi api` for scripts, inspection, and integrations.

Start here:

- [Single-agent / single-wallet usage](single-agent.md)
- [Human operator workflows](human-usage.md)
- [Multi-agent profiles](multi-agent.md)
- [Preferences and hard filters](preferences.md)
- [OpenClaw allocator workflow](openclaw.md)
- [OpenClaw Vaults CLI skill](../skills/openclaw-vaultsfyi-cli/SKILL.md)
- [Decision packet and validation model](decisions.md)
- [Command reference](commands.md)
- [Safety model](safety.md)
