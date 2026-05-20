# Preferences

Preferences are reusable hard filters for vault eligibility.

They do not choose a vault. They define what vaults are allowed to be considered.

## Create a preference

```bash
vaultsfyi preference init blue-chip
vaultsfyi preference set blue-chip min_tvl 10000000
vaultsfyi preference set blue-chip min_apy 0.02
vaultsfyi preference set blue-chip max_apy 0.15
vaultsfyi preference set blue-chip min_vault_score 8
vaultsfyi preference set blue-chip tags stablecoin,blue-chip
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
# max_tvl = 50000000
min_apy = 0.02
max_apy = 0.15
apy_interval = "7day"
# min_vault_score = 8
only_transactional = true
# only_app_featured = true
allow_corrupted = false
# allow_vaults_with_warnings = false
vault_whitelist = []
allowed_assets = ["USDC"]
disallowed_assets = []
allowed_networks = ["base", "mainnet"]
disallowed_networks = []
allowed_protocols = ["aave", "morpho", "euler"]
disallowed_protocols = []
tags = ["stablecoin"]
curators = []
# sort_by = "apy7day" # tvl | apy1day | apy7day | apy30day
# sort_order = "desc" # asc | desc
# page = 0
# per_page = 50
```

## Semantics

- `page` / `per_page`: optional local page slice after all filters and sorting
- `allowed_assets`: asset symbols to include; defaults to the strategy `asset` when empty
- `disallowed_assets`: asset symbols to exclude; ignored when `allowed_assets` is set
- `allowed_networks`: network names or CAIP-2 IDs to include; defaults to the strategy `network` when empty
- `disallowed_networks`: network names or CAIP-2 IDs to exclude; ignored when `allowed_networks` is set
- `allowed_protocols`: if non-empty, only these protocol names are allowed
- `disallowed_protocols`: protocols to exclude; `blocked_protocols` remains supported as a legacy alias
- `min_tvl`: minimum vault TVL in USD
- `max_tvl`: maximum vault TVL in USD
- `min_apy`: minimum APY as decimal, e.g. `0.05` for 5%; applied to the configured APY interval when returned by the API, otherwise total APY
- `max_apy`: maximum APY as decimal, useful to avoid suspicious/reward-heavy spikes; uses the same APY source as `min_apy`
- `apy_interval`: preferred APY interval for APY filtering, usually `1day`, `7day`, or `30day`
- `min_vault_score`: minimum vaults.fyi vault score when score data is present
- `only_transactional`: require vaults that can be transacted through vaults.fyi
- `only_app_featured`: when true, require vaults featured in app.vaults.fyi
- `allow_corrupted`: when false, exclude vaults marked corrupted
- `allow_vaults_with_warnings`: when false, exclude vaults with warnings or flags
- `tags`: require all listed tags
- `curators`: if non-empty, only these curators are allowed; `allowed_curators` remains supported as a legacy alias
- `sort_by`: sort field, one of `tvl`, `apy1day`, `apy7day`, `apy30day`
- `sort_order`: `asc` or `desc`
- `vault_whitelist`: if non-empty, only these vault addresses are allowed

These names are snake_case versions of the vaults.fyi `/v2/detailed-vaults` filters. The CLI sends the filters supported by the active vaults.fyi endpoint and applies the remaining detailed-vault filters locally to the returned opportunities.

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
