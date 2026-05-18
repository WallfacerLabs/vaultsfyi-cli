# Preferences

Preferences are reusable hard filters for vault eligibility.

They do not choose a vault. They define what vaults are allowed to be considered.

## Create a preference

```bash
vaultsfyi preference init blue-chip
vaultsfyi preference set blue-chip min_tvl 10000000
vaultsfyi preference set blue-chip min_apy 0.02
vaultsfyi preference set blue-chip max_apy 0.15
vaultsfyi preference set blue-chip allowed_protocols aave,morpho,euler
vaultsfyi preference show blue-chip
```

## Use a preference

```bash
vaultsfyi opportunities --preference blue-chip
vaultsfyi deploy --percent 10 --preference blue-chip
vaultsfyi decision-packet --preference blue-chip -o json
```

## Fields

Supported preference fields:

```toml
[preferences.blue-chip]
min_tvl = 10000000
min_apy = 0.02
max_apy = 0.15
only_transactional = true
vault_whitelist = []
allowed_protocols = ["aave", "morpho", "euler"]
blocked_protocols = []
allowed_curators = []
```

## Semantics

- `min_tvl`: minimum vault TVL in USD
- `min_apy`: minimum APY as decimal, e.g. `0.05` for 5%
- `max_apy`: maximum APY as decimal, useful to avoid suspicious/reward-heavy spikes
- `only_transactional`: require vaults that can be transacted through vaults.fyi
- `vault_whitelist`: if non-empty, only these vault addresses are allowed
- `allowed_protocols`: if non-empty, only these protocol names are allowed
- `blocked_protocols`: protocols to exclude
- `allowed_curators`: if non-empty, only these curators are allowed

## Precedence

For a command:

```bash
vaultsfyi --agent conservative deploy --percent 10 --preference blue-chip
```

Resolution order:

1. global defaults
2. global config
3. agent profile overlay
4. selected preference overlay into strategy filters
5. explicit command flags

Preferences are hard boundaries for OpenClaw decisions. A decision targeting a vault outside the selected preference fails validation.
