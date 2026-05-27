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

Create a capped bucket-style preference:

```bash
vaultsfyi preference init degen
vaultsfyi preference set degen allowed_protocols spicy-protocol
vaultsfyi preference set degen bucket_max_pct 10
vaultsfyi preference set degen bucket_tolerance_pct 5
```

## Use a preference

```bash
vaultsfyi opportunities --preference blue-chip
vaultsfyi deploy --percent 10 --preference blue-chip
vaultsfyi decision-packet --preference blue-chip -o json
vaultsfyi --agent conservative config set agent.preference blue-chip
vaultsfyi agent run conservative --dry-run
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
# bucket_max_pct = 10 # no new deploy/rebalance-in above 10% portfolio exposure
# bucket_tolerance_pct = 5 # drift band; status becomes over_tolerance above 15%
# only_instant_deposit = true # require instant deposit steps
# only_instant_redeem = true # require instant withdrawal steps
# max_performance_fee = 0.20 # exclude vaults with performance fee above 20%
# max_management_fee = 0.02 # exclude vaults with management fee above 2%
# max_withdrawal_fee = 0.01 # exclude vaults with withdrawal fee above 1%
# max_deposit_fee = 0.005 # exclude vaults with deposit fee above 0.5%
# min_remaining_capacity = 100000 # exclude vaults with remaining capacity below 100k USD
# only_rewards_supported = true # require vaults that support rewards
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
- `bucket_max_pct`: optional maximum active allocation for this preference bucket as a percent of total portfolio value. New deploys and rebalances into the preference are capped at the remaining room below this value.
- `bucket_tolerance_pct`: optional absolute percentage-point drift band above `bucket_max_pct`. For example, `bucket_max_pct = 10` and `bucket_tolerance_pct = 5` allows market growth to 15% before the packet reports `over_tolerance`. It does not allow new capital above 10%.
- `only_instant_deposit`: when true, exclude vaults whose `depositStepsType` is not `"instant"`
- `only_instant_redeem`: when true, exclude vaults whose `redeemStepsType` is not `"instant"`
- `max_performance_fee`: exclude vaults with a performance fee above this decimal threshold; vaults missing the field are kept
- `max_management_fee`: exclude vaults with a management fee above this decimal threshold; vaults missing the field are kept
- `max_withdrawal_fee`: exclude vaults with a withdrawal fee above this decimal threshold; vaults missing the field are kept
- `max_deposit_fee`: exclude vaults with a deposit fee above this decimal threshold; vaults missing the field are kept
- `min_remaining_capacity`: exclude vaults with remaining capacity below this USD value; vaults missing the field are kept
- `only_rewards_supported`: when true, exclude vaults where `rewardsSupported` is not true

Most filter names are snake_case versions of the vaults.fyi `/v2/detailed-vaults` filters. The CLI sends the filters supported by the active vaults.fyi endpoint and applies the remaining detailed-vault filters locally to the returned opportunities. Bucket fields are local CLI policy and are not sent as vaults.fyi API filters.

## Bucket Limits

Preference buckets are enforced for commands that select a preference, including
`agent run` when the profile sets `agent.preference`:

```bash
vaultsfyi deploy --percent 10 --preference degen
vaultsfyi decision-packet --preference degen -o json
vaultsfyi --agent opportunistic config set agent.preference degen
vaultsfyi agent run opportunistic --dry-run
```

The CLI estimates bucket exposure by matching current position vault addresses
against the selected preference's eligible vaults and any `vault_whitelist`
addresses. If a degen bucket has `bucket_max_pct = 10`, a 100 USDC portfolio
with 8 USDC already in degen vaults can only add 2 USDC more, even if the
requested deploy size is larger.

The tolerance band is informational for decision packets and agent-run status:

- below `bucket_max_pct`: `under_limit`
- at or above `bucket_max_pct`, up to `bucket_max_pct + bucket_tolerance_pct`: `within_tolerance`
- above the tolerance band: `over_tolerance`

The current candidate set can prevent additional exposure above the max. It
does not yet emit a cross-preference "sell degen into blue-chip" candidate; that
would require a multi-preference allocator view.

## Precedence

The CLI builds one effective config for each command. Later layers override
earlier layers when they set the same key.

For a command:

```bash
vaultsfyi --agent conservative deploy --percent 10 --preference blue-chip
```

Resolution order, from lowest to highest priority:

1. global defaults: built into the CLI. These are used when no config file sets a value.
2. global config: `~/.config/vaultsfyi/config.toml`, or `$XDG_CONFIG_HOME/vaultsfyi/config.toml` when `XDG_CONFIG_HOME` is set.
3. agent profile overlay: `~/.config/vaultsfyi/agents/conservative.toml` when `--agent conservative` is used. This can override any normal config section, such as `wallet`, `strategy`, `risk`, `execution`, or `decision`.
4. environment overrides: only the mapped runtime fields below, such as wallet, RPC, and vaults.fyi API settings.
5. selected preference overlay: `[preferences.blue-chip]` is copied into `strategy` because `--preference blue-chip` was passed, or because `agent.preference = "blue-chip"` is configured for `agent run`.
6. explicit command flags: command-specific flags such as `--percent 10`, `--preference NAME`, `--dry-run`, `--yes`, or `--execute`.

For `agent run NAME`, `agent.preference` must be set in that named profile.
Global `agent.preference` is not inherited by named profile runs.

Environment overrides are:

```bash
OWS_WALLET
OWS_CHAIN
OWS_VAULT_PATH
OWS_CLI_PATH
BASE_RPC_URL
VAULTS_API_KEY
VAULTS_API_URL
```

Example:

```toml
# global config
[strategy]
min_tvl = 1000000
allowed_networks = ["base"]

# agent profile for --agent conservative
[strategy]
min_tvl = 5000000

# selected preference for --preference blue-chip
[preferences.blue-chip]
min_tvl = 10000000
allowed_protocols = ["morpho"]
```

The effective command uses `min_tvl = 10000000`, `allowed_networks = ["base"]`,
and `allowed_protocols = ["morpho"]`. The preference does not rewrite the config
file; it only overlays the in-memory config for that command or agent run.

Preferences are hard boundaries for OpenClaw decisions. A decision targeting a vault outside the selected preference fails validation.
