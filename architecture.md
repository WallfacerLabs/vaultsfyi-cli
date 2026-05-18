# DeFi Agent Architecture

## Purpose

This project builds the **mechanics and building blocks** for a DeFi capital management agent. It is **not** an autonomous agent but rather a collection of composable functions that demonstrate how an agent would interact with DeFi protocols.

The agent manages USDC on Base network, deploying idle capital into yield-generating vaults and managing positions through the vaults.fyi API with x402 payment protocol.

## Design Principles

1. **Simplicity First**: Minimize complexity, build only what's needed for the showcase
2. **Stateless Operation**: No persistent storage, query fresh state each run
3. **Single Asset Focus**: USDC only on Base network
4. **User-Initiated**: User runs commands, agent executes them (no autonomous operation)
5. **Composable Mechanics**: Each function is independent and can be combined
6. **Smart Diversification**: Automatically avoid deploying to vaults with existing positions
7. **Pay-per-use**: Use x402 protocol for API access (pay in USDC per request)

## Core Capabilities

The agent can:
- **Discover** idle USDC in wallet
- **Analyze** available yield opportunities
- **Select** best vaults based on criteria and existing positions
- **Deploy** capital to selected vaults
- **Monitor** active positions across vaults
- **Redeem** capital from positions (partial or full)
- **Execute** blockchain transactions (sign, estimate gas, broadcast, confirm)

## Architecture Overview

### Four-Layer Design

```
┌─────────────────────────────────────────────────────────┐
│  USER INTERFACE (Interactive Python)                    │
│  - Import Agent class                                   │
│  - Call methods: deploy_capital(), show_positions()     │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  ORCHESTRATION LAYER (agent/agent.py)                   │
│  - Agent class with high-level methods                  │
│  - Coordinates between API, Strategy, and Core layers   │
│  - Formats and displays results to user                 │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ API LAYER    │  │ STRATEGY     │  │ CORE LAYER   │
│              │  │ LAYER        │  │              │
│ - x402       │  │              │  │ - Wallet     │
│   client     │  │ - Vault      │  │ - TX signing │
│ - Positions  │  │   selection  │  │ - TX         │
│ - Opportuni- │  │ - Criteria   │  │   broadcast  │
│   ties       │  │   filtering  │  │ - Gas        │
│ - TX         │  │ - Diversifi- │  │   estimation │
│   generation │  │   cation     │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┴─────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌──────────────┐                  ┌──────────────┐
│ vaults.fyi   │                  │ Base Network │
│ API          │                  │ RPC          │
│ (x402)       │                  │              │
└──────────────┘                  └──────────────┘
```

## Module Structure

```
defi_agent/
├── config.yaml                 # User configuration (criteria, limits)
├── config.yaml.example         # Template with defaults
├── .env                        # OWS wallet config (no OWS signing keys)
├── .env.example                # Template
├── requirements.txt            # Python dependencies
├── README.md                   # Usage guide and examples
├── architecture.md             # This file
│
├── agent/
│   ├── __init__.py            # Exports Agent class
│   ├── agent.py               # Main Agent class (Orchestration Layer)
│   ├── display.py             # Display utilities (colors, formatting, tables)
│   ├── utils.py               # Transaction manipulation utilities
│   │
│   ├── api/                   # API Layer - vaults.fyi interactions
│   │   ├── __init__.py
│   │   ├── client.py          # x402 client wrapper (payment + requests)
│   │   ├── positions.py       # get_positions(), get_idle_assets()
│   │   ├── opportunities.py   # get_best_deposit_options()
│   │   └── transactions.py    # generate_deposit_tx(), generate_redeem_tx()
│   │
│   ├── strategy/              # Strategy Layer - decision making
│   │   ├── __init__.py
│   │   ├── selector.py        # OpportunitySelector class
│   │   └── criteria.py        # Vault filtering and scoring logic
│   │
│   └── core/                  # Core Layer - blockchain operations
│       ├── __init__.py
│       ├── executor.py        # Transaction execution (sign, broadcast, confirm)
│       └── wallet.py          # OWS wallet utilities (wallet lookup/address)
│
└── examples/
    ├── basic_usage.py         # Demo: full flow (deploy → positions → redeem)
    └── interactive.py         # Demo: interactive Python session guide
```

## Layer Responsibilities

### 1. Orchestration Layer (`agent/agent.py`)

**Responsibility**: High-level workflow coordination and user interaction.

**Key Class**: `Agent`

**Methods**:
- `show_state()` - Display gas balance (ETH), USDC balance, and positions summary
- `deploy_capital(percent: float)` - Deploy X% of idle capital to a vault
- `show_positions()` - Display current vault positions (with retry logic, filters zero-balance)
- `show_idle_assets()` - Display idle USDC balance
- `redeem(position_nickname: str, percent: float)` - Redeem from specific position by nickname
- `redeem_all()` - Redeem all positions completely

**Behavior**:
- Loads configuration from `config.yaml`
- Coordinates calls between API, Strategy, and Core layers
- **Validates gas balance upfront** before any transaction operations
- **Validates minimum deposit amount** ($0.10) before deploying
- Formats and prints results to console using display utilities (2 decimal places for USD)
- Handles verbose/concise error display modes
- Validates inputs before processing
- **Generates 10-character nicknames** from vault names (first 10 chars, spaces removed)
- **Retries position display** after deployment (3 attempts, 5s delay)
- **Handles floating-point precision** for 100% redemptions to avoid rounding errors

### 2. Display Utilities (`agent/display.py`)

**Responsibility**: Terminal output formatting with colors and enhanced UX.

**Key Functions**:
- `format_state_summary()` - Format gas, USDC, and position summary
- `format_positions_table()` - Create colorized table of positions
- `format_deploy_success()` - Success message for deployments
- `format_redeem_success()` - Success message for redemptions
- `format_error()` - Error message formatting
- `section_header()`, `subsection_header()` - Section formatting
- `highlight_currency()`, `highlight_percentage()` - Value highlighting

**Features**:
- ANSI color support detection
- Automatic color disable for non-TTY environments
- Consistent formatting across all output
- Enhanced readability with visual hierarchy

### 3. Transaction Utilities (`agent/utils.py`)

**Responsibility**: Transaction data manipulation utilities.

**Key Functions**:
- `modify_erc20_approve_amount()` - Modify approval amount in transaction data
- `increase_approval_buffer()` - Add buffer to approval amounts (10% default)

**Purpose**:
- Handle ERC20 approve transaction encoding/decoding
- Add safety buffers to approvals for vault fees and slippage
- Direct transaction data manipulation

### 4. API Layer (`agent/api/`)

**Responsibility**: Interact with vaults.fyi API using x402 payment protocol.

#### `client.py` - x402 Client

**Purpose**: Handle x402 payment protocol for API requests.

**Key Functions**:
- `make_x402_request(url, method='GET', params=None)` - Execute paid API request
- Flow: Initial 402 → Payment → Retry with proof → Return data

**Based on**: `api-tests/config/payment_utils.py` patterns

#### `positions.py` - Position Management

**Purpose**: Query user's current state.

**Key Functions**:
- `get_positions(wallet_address: str)` → List of vault positions
  - Returns: vault_address, vault_name, asset, apy, balance_usd, network, nickname
  - **Filters out zero-balance positions**
  - **Generates 10-char nickname**: First 10 chars of vault name (spaces removed)
  - Example: "Yearn USDC Vault" → "YearnUSDCV", "Gauntlet Aave USDC" → "GauntletAa"
- `get_idle_assets(wallet_address: str)` → Idle USDC balance
  - Returns: usdc_balance (float)

**API Endpoints Used**:
- `GET /v2/portfolio/positions/{userAddress}`
- `GET /v2/portfolio/idle-assets/{userAddress}`

#### `opportunities.py` - Opportunity Discovery

**Purpose**: Find available vaults to deploy capital using API-side filtering.

**Key Functions**:
- `get_best_deposit_options(wallet_address: str, criteria: dict)` → List of opportunities
  - Builds query parameters from criteria dict
  - Returns: vault_address, vault_name, apy, tvl, network, asset

**API Parameters Passed** (from criteria config):
- `allowedAssets`: ["USDC"] - Only USDC vaults
- `allowedNetworks`: ["base"] - Only Base network
- `minTvl`: From config (e.g., 1000000)
- `minApy`: From config (e.g., 0.01)
- `onlyTransactional`: true - Only vaults supporting transactions
- `apyInterval`: "1day" - **Always use 1-day APY** (requirement Q27)
- `minUsdAssetValueThreshold`: 1 - Minimum USD value to consider

**API Endpoints Used**:
- `GET /v2/portfolio/best-deposit-options/{userAddress}?allowedAssets=USDC&allowedNetworks=base&minTvl=1000000&minApy=0.01&onlyTransactional=true&apyInterval=1day`

#### `transactions.py` - Transaction Generation

**Purpose**: Generate transaction payloads for vault operations.

**Key Functions**:
- `generate_deposit_tx(user_address, vault_address, amount, asset_address, network)` → Transaction payloads
  - Returns: **list[dict]** - Multiple transactions (e.g., approve + deposit)
  - Each dict: {to, data, value}
- `generate_redeem_tx(user_address, vault_address, amount, asset_address, network, is_full_redemption)` → Transaction payload
  - Returns: **list[dict]** - Transaction(s) for redemption
  - **Only uses default step** (no multi-step redemptions)
  - **Handles floating-point precision** for 100% redemptions by subtracting 1 wei
  - Each dict: {to, data, value}

**API Endpoints Used**:
- `GET /v2/transactions/deposit/{userAddress}/{network}/{vaultAddress}?amount={amount}&assetAddress={assetAddress}`
- `GET /v2/transactions/redeem/{userAddress}/{network}/{vaultAddress}?amount={amount}&assetAddress={assetAddress}`

### 5. Strategy Layer (`agent/strategy/`)

**Responsibility**: Decision-making logic for vault selection.

#### `selector.py` - OpportunitySelector

**Purpose**: Choose which vault to deploy capital to.

**Key Class**: `OpportunitySelector`

**Methods**:
- `select_vault(opportunities, existing_positions, criteria)` → Selected vault

**Logic Flow**:
1. API returns pre-filtered opportunities (by APY, TVL, network, asset, etc.)
2. Apply vault whitelist if configured (client-side)
3. Exclude vaults where user already has positions (diversification)
4. Return first qualifying vault
5. If no qualifying vaults, return None

**Behavior**:
- **API-side filtering**: APY, TVL, network, asset, transactional status (fast, efficient)
- **Client-side filtering**: Vault whitelist, existing positions (simple, minimal)
- Smart diversification: Never picks a vault user already invested in
- Deterministic: Same inputs → same output (no randomness)

#### `criteria.py` - Client-Side Filtering

**Purpose**: Apply client-side filters that API doesn't support.

**Key Functions**:
- `apply_vault_whitelist(vaults, whitelist)` → Filtered list
  - If whitelist is not empty, only return vaults in the whitelist
  - If whitelist is empty, return all vaults (no filtering)
- `exclude_existing_positions(vaults, positions)` → Filtered list
  - Removes vaults where user already has positions (for diversification)

**Note**: Most criteria filtering (APY, TVL, network, asset, transactional) is done by the API via query parameters.

### 6. Core Layer (`agent/core/`)

**Responsibility**: Blockchain interactions (wallet, transactions).

#### `wallet.py` - Wallet Management

**Purpose**: Handle OWS wallet lookup and public account metadata. Key material remains inside the OWS vault.

**Key Functions**:
- `get_address()` → OWS EVM wallet address (string)
- `get_balance(network='base')` → ETH balance (for gas)

**Uses**: `open-wallet-standard` Python bindings

#### `executor.py` - Transaction Executor

**Purpose**: Sign, estimate gas, broadcast, and confirm transactions.

**Key Class**: `TransactionExecutor`

**Methods**:
- `check_gas_balance()` → dict with ETH balance and sufficiency check
- `execute(tx_payload, wait_for_confirmation=True)` → tx_hash
- `execute_multiple(tx_payloads)` → list of tx_hashes

**Flow**:
1. **Check ETH balance for gas** (requirement Q1)
2. Estimate gas using `web3.eth.estimate_gas()`
3. Set gas limit and gas price
4. Serialize the unsigned transaction and request an OWS signature
5. Assemble the signed raw transaction
6. Broadcast transaction to Base RPC
7. Wait for confirmation (optional)
8. Return transaction hash

**Multi-Transaction Handling** (requirement Q23):
- Execute approve + deposit transactions sequentially
- **Never revoke approvals** on failure (requirement Q24)
- All transactions must succeed for operation to complete

**Gas Strategy**:
- Use `eth.estimate_gas()` for gas limit
- Use network's suggested gas price (or default)
- No user configuration needed (sensible defaults)

**Uses**: `web3.py`, `open-wallet-standard`, `eth-account` transaction encoding helpers

## Configuration

### config.yaml

User-configurable settings for agent behavior.

```yaml
# Network Configuration
network: base
rpc_url: null  # Will use BASE_RPC_URL from .env

# Asset Configuration
asset: USDC
asset_address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# API Configuration
vaults_api_url: https://api.vaults.fyi

# Investment Rules
investment:
  max_allocation_per_vault: 0.10  # 10% max per vault
  min_deposit_usd: 0.10            # $0.10 minimum deposit

# Vault Selection Criteria (passed as API parameters)
criteria:
  min_apy: 0.01                    # 1% minimum APY
  min_tvl: 100000000               # $100M minimum TVL
  only_transactional: true         # Only vaults supporting transactions
  apy_interval: "1day"             # Always use 1-day APY

# Display Configuration
display:
  decimals: 2                      # Show 2 decimal places for USD
  position_retry_attempts: 3       # Retry position display after deployment
  position_retry_delay: 5          # Wait 5 seconds between retries

# Vault Whitelist (optional - client-side filtering)
# Leave empty array [] to allow all vaults that pass criteria
vault_whitelist: []

# Verbose error messages
verbose: false
```

### .env

Local wallet configuration. Do not commit real passphrases or API tokens.

```bash
# OWS wallet name/UUID used for vault transactions and x402 payments
OWS_WALLET=agent-treasury
OWS_CHAIN=base
# Optional: OWS_PASSPHRASE=wallet-passphrase-or-scoped-ows-token

# Optional: Custom RPC endpoint
# RPC_URL=https://base-mainnet.infura.io/v3/YOUR-PROJECT-ID
```

## Data Flow: deploy_capital(10)

**Step-by-step execution**:

1. **Check Gas Balance Upfront** (requirement Q1)
   - Call `core.executor.check_gas_balance()`
   - If insufficient ETH: Fail with clear message
   - Example: "Need 0.0023 ETH for gas, have 0.0010 ETH"

2. **Get Idle Assets**
   - Call `api.positions.get_idle_assets(wallet_address)`
   - x402 payment: ~$0.01 USDC
   - Result: `idle_usdc = 100.0` (example)

3. **Calculate Deploy Amount**
   - `deploy_amount = idle_usdc * (percent / 100)`
   - Example: `100 * 0.10 = 10 USDC`

4. **Validate Minimum Deposit** (requirement Q5)
   - If `deploy_amount < 0.10`: Fail with message
   - Example: "Deposit amount $0.05 below minimum $0.10"

5. **Get Existing Positions**
   - Call `api.positions.get_positions(wallet_address)`
   - x402 payment: ~$0.01 USDC
   - Extract vault addresses: `existing_vaults = ['0xA...', '0xB...']`
   - Positions include generated nicknames

6. **Get Opportunities (with API Filtering)**
   - Build API query parameters from config criteria:
     - `allowedAssets=USDC`
     - `allowedNetworks=base`
     - `minTvl=1000000`
     - `minApy=0.01`
     - `onlyTransactional=true`
     - `apyInterval=1day`
   - Call `api.opportunities.get_best_deposit_options(wallet_address, criteria)`
   - x402 payment: ~$0.01 USDC
   - Result: Pre-filtered list of vault opportunities (API already filtered by APY, TVL, etc.)

7. **Select Vault (Strategy Layer - Minimal Client-Side Filtering)**
   - Apply vault whitelist if configured (only keep whitelisted vaults)
   - Exclude vaults in `existing_vaults` (diversification)
   - Pick first qualifying vault: `selected_vault`
   - If none qualify → error: "No suitable vaults available" with detailed reason

8. **Generate Transaction(s)**
   - Call `api.transactions.generate_deposit_tx(wallet_address, selected_vault, deploy_amount, usdc_address, 'base')`
   - x402 payment: ~$0.01 USDC
   - Result: **list[dict]** - typically `[approve_tx, deposit_tx]`

9. **Execute Transactions** (requirement Q23, Q24)
   - Call `core.executor.execute_multiple(tx_payloads)`
   - For each transaction:
     - Sign through OWS (`sign_transaction`) without exposing OWS signing keys
     - Estimate gas → set gas limit
     - Broadcast to Base network
     - Wait for confirmation
   - **Execute sequentially** (approve then deposit)
   - **Never revoke approvals** on failure
   - Result: `tx_hashes = ['0x...', '0x...']`

10. **Display Success**
   - Print: "✓ Deployed $10.00 USDC to [Vault Name]" (2 decimal places, Q26)
   - Print: "Transactions: 0x... (approve), 0x... (deposit)"
   - Call `show_positions()` with retry logic to display updated state (requirement Q17)
     - Retry up to 3 times with 5 second delays if position not found
     - This handles API indexer lag

**Total Cost**:
- x402 API payments: ~$0.04 USDC (4 requests)
- Gas fees: ~$0.01 ETH (varies with network congestion)

## Data Flow: show_positions()

1. **Get Positions**
   - Call `api.positions.get_positions(wallet_address)`
   - x402 payment: ~$0.01 USDC

2. **Filter Zero-Balance Positions** (requirement Q12)
   - Remove positions with balance_usd <= 0

3. **Format Display**
   - Extract: nickname, vault_name, asset, apy (1-day), balance_usd
   - Create table with columns:
     ```
     Nickname    | Vault Name              | Asset | APY (1d) | Balance
     ------------|-------------------------|-------|----------|----------
     YearnUSDCV  | Yearn USDC Vault        | USDC  | 5.23%    | $10.00
     AaveUSDCVa  | Aave USDC Vault         | USDC  | 4.85%    | $15.50
     ```
   - **Display 2 decimal places** for USD amounts (requirement Q26)
   - **Display 1-day APY** (requirement Q27)

4. **Print to Console**
   - Use `tabulate` or simple formatting
   - Show total balance: "Total: $25.50"

## Data Flow: redeem(position_nickname, percent)

Example: `agent.redeem('YearnUSDCV', 50)` - Redeem 50% from position by nickname

1. **Check Gas Balance Upfront** (requirement Q1)
   - Call `core.executor.check_gas_balance()`
   - If insufficient ETH: Fail with clear message

2. **Get Positions**
   - Call `api.positions.get_positions(wallet_address)`
   - x402 payment: ~$0.01 USDC
   - Find position by nickname: `position = find_by_nickname('YearnUSDCV')`
   - If not found: Fail with message

3. **Calculate Redeem Amount**
   - Get position balance: `balance_lp_tokens = position.balance_lp_tokens`
   - Calculate: `redeem_lp_tokens = balance_lp_tokens * (percent / 100)`
   - Convert to wei using LP token decimals
   - **Detect full redemption**: If percent >= 99.99%, set `is_full_redemption = True`

4. **Generate Redeem Transaction**
   - Call `api.transactions.generate_redeem_tx(wallet, vault, redeem_lp_tokens, lp_decimals, usdc_address, 'base', is_full_redemption)`
   - x402 payment: ~$0.01 USDC
   - **Precision handling**: If `is_full_redemption=True`, subtracts 1 wei from amount to avoid floating-point rounding errors
   - Result: **list[dict]** - Uses default step only (no multi-step redemption)

5. **Execute Transaction(s)**
   - Call `core.executor.execute_multiple(tx_payloads)` if multiple, or `execute()` if single
   - Sign, estimate gas, broadcast, confirm
   - Result: `tx_hash(es) = '0x...'`

6. **Display Success**
   - Print: "✓ Redeemed $5.00 USDC from [Vault Name]" (2 decimals, Q26)
   - Print: "Transaction: 0x..."
   - Call `show_positions()` to show updated state (zero-balance positions filtered out)

## Error Handling

### Philosophy

**Fail fast, inform user clearly**. No retries, no silent failures.

### Error Types

1. **Configuration Errors**
   - Missing OWS wallet or invalid OWS configuration
   - Invalid config.yaml format
   - Action: Print error, exit immediately

2. **API Errors**
   - x402 payment failure (insufficient USDC)
   - API returns 4xx/5xx
   - Action: Print error message, raise exception

3. **Insufficient Funds**
   - Not enough idle USDC to deploy
   - Not enough ETH for gas
   - Action: Print clear message, exit

4. **No Suitable Vaults**
   - All vaults filtered out by criteria
   - All vaults already have positions
   - Action: Print explanation, suggest adjusting criteria

5. **Transaction Failures**
   - Transaction reverted on-chain
   - Gas estimation failed
   - Action: Print error + transaction hash (if available)

### Verbose Mode

Controlled by `config.yaml: verbose: true/false`

**Concise Mode** (default):
```
ERROR: Insufficient USDC for deployment
```

**Verbose Mode**:
```
ERROR: Insufficient USDC for deployment
Details:
  - Required: $10.00 USDC
  - Available: $5.00 USDC
  - Shortfall: $5.00 USDC

Traceback:
  File "agent.py", line 42, in deploy_capital
    raise InsufficientFundsError(...)
```

## Dependencies

**Core Libraries**:
- `web3>=6.0.0` - Ethereum blockchain interaction
- `eth-account>=0.8.0` - EVM transaction encoding helpers (not key custody)
- `requests>=2.25.0` - HTTP requests (for x402)
- `python-dotenv>=0.19.0` - Environment variable management
- `pyyaml>=6.0` - YAML config parsing
- `tabulate>=0.9.0` - Table formatting for displays

**x402 Protocol**:
- OWS CLI - `ows pay request` for x402-paid API calls

**Note**: Reusing patterns from `api-tests` but not importing that codebase directly.

## Example Usage

### Basic Flow

```python
# Import agent
from agent import Agent

# Initialize
agent = Agent()

# Check current state (gas, USDC, positions)
agent.show_state()
# Output:
# Gas Balance: 0.0523 ETH
# USDC Balance: $100.00
# Active Positions: 0

# Check idle capital
agent.show_idle_assets()
# Output: Idle USDC: $100.00

# Deploy 10% to a vault
agent.deploy_capital(10)
# Output:
# ✓ Deployed $10.00 USDC to Yearn USDC Vault
# Transaction: 0x1234...
#
# Current Positions:
# Nickname    | Vault Name         | Asset | APY (1d) | Balance
# ------------|-------------------|-------|----------|----------
# YearnUSDCV  | Yearn USDC Vault  | USDC  | 5.23%    | $10.00

# Deploy another 10% (goes to different vault automatically)
agent.deploy_capital(10)
# Output:
# ✓ Deployed $10.00 USDC to Aave USDC Vault
# Transactions: 0x5678... (approve), 0x5679... (deposit)
#
# Current Positions:
# Nickname    | Vault Name         | Asset | APY (1d) | Balance
# ------------|-------------------|-------|----------|----------
# YearnUSDCV  | Yearn USDC Vault  | USDC  | 5.23%    | $10.00
# AaveUSDCVa  | Aave USDC Vault   | USDC  | 4.85%    | $10.00

# Show positions
agent.show_positions()

# Redeem 50% from position by nickname
agent.redeem('YearnUSDCV', 50)
# Output:
# ✓ Redeemed $5.00 USDC from Yearn USDC Vault
# Transaction: 0x9abc...
#
# Current Positions:
# Nickname    | Vault Name         | Asset | APY (1d) | Balance
# ------------|-------------------|-------|----------|----------
# YearnUSDCV  | Yearn USDC Vault  | USDC  | 5.23%    | $5.00
# AaveUSDCVa  | Aave USDC Vault   | USDC  | 4.85%    | $10.00

# Redeem all positions
agent.redeem_all()
# Output:
# ✓ Redeemed $5.00 USDC from Yearn USDC Vault (Transaction: 0xdef1...)
# ✓ Redeemed $10.00 USDC from Aave USDC Vault (Transaction: 0xdef2...)
#
# All positions closed.
```

## Design Decisions & Rationale

### Why Stateless?

**Decision**: No database, no state files, query fresh each time.

**Rationale**:
- Simplifies architecture (no storage layer needed)
- Always accurate (blockchain is source of truth)
- Easier to debug (no stale state issues)
- Focus on mechanics, not state management

**Trade-off**: More x402 API costs per operation, but acceptable for showcase.

### Why Single Asset (USDC)?

**Decision**: Only manage USDC on Base.

**Rationale**:
- Simplifies multi-asset logic (no token conversions)
- USDC is most common DeFi asset
- Base has low fees and good USDC liquidity
- Easy to extend to other assets later

**Trade-off**: Less flexible, but enough for demonstration.

### Why API-Side Filtering?

**Decision**: Use API query parameters for criteria filtering instead of client-side filtering.

**Rationale**:
- Reduces API response payload (only get vaults that match criteria)
- Faster (filtering done on server with optimized database queries)
- Less x402 payment cost (smaller response = lower cost)
- Simpler client code (no need to iterate and filter locally)
- More accurate (API has access to latest data)

**Trade-off**: Less flexible (can only use filters API provides), but sufficient for our use case.

### Why Vault Whitelist?

**Decision**: Support optional vault whitelist in config for extra safety.

**Rationale**:
- Security: Users can restrict agent to only deploy to trusted/audited vaults
- Control: Users can limit to specific strategies or protocols
- Testing: Easy to test with a small subset of vaults
- Optional: Empty whitelist = no restriction (all qualifying vaults allowed)

**Trade-off**: Requires manual vault address configuration, but provides peace of mind.

### Why Position-Aware Diversification?

**Decision**: Automatically skip vaults with existing positions.

**Rationale**:
- Natural diversification without complex logic
- Prevents over-allocation to single vault
- User can call `deploy_capital(10)` multiple times and get different vaults
- Simpler than round-robin with state tracking

**Trade-off**: User can't add to existing positions (but can redeem + redeploy).

### Why x402 Instead of API Key?

**Decision**: Use x402 payment protocol for all API calls.

**Rationale**:
- Demonstrates pay-per-use model (relevant for agent economics)
- No API key management needed for vaults.fyi; OWS may use scoped local API tokens for agent signing access
- Payment = authentication; OWS signs payment proofs outside the agent process
- Showcases blockchain-native access control

**Trade-off**: Small USDC cost per request (~$0.01), but aligns with project goals.

### Why web3.py for Gas Estimation?

**Decision**: Use `eth.estimate_gas()` with no user configuration.

**Rationale**:
- Accurate gas estimates (simulates transaction)
- No manual gas limit tuning needed
- Reduces configuration complexity
- Standard practice in web3 development

**Trade-off**: Slightly slower (extra RPC call), but more reliable.

## Future Extensions

**What this architecture enables** (not implemented in v1):

1. **Multi-Asset Support**: Extend strategy layer to handle ETH, wETH, DAI, etc.
2. **Advanced Strategies**: Implement scoring algorithms, rebalancing logic
3. **Position Monitoring**: Track APY changes, suggest rebalancing
4. **Multi-Chain**: Support Ethereum, Arbitrum, Optimism (same patterns)
5. **Autonomous Operation**: Add scheduler, run strategies periodically
6. **Risk Management**: Position limits, stop-loss triggers
7. **Historical Tracking**: Save decisions and outcomes for learning
8. **Gas Optimization**: Batch transactions, use gas price oracles

**The mechanics built here are the foundation for all of these.**

## Success Criteria

This architecture is successful if:

1. ✅ User can deploy capital with one simple call: `agent.deploy_capital(10)`
2. ✅ Agent handles all complexity: idle detection, vault selection, transaction execution
3. ✅ Clear separation of concerns: API, Strategy, Core, Orchestration
4. ✅ Easy to understand and extend (well-documented, modular)
5. ✅ Demonstrates real DeFi interactions (not mocked)
6. ✅ Automatic diversification without user intervention
7. ✅ Clean error handling with helpful messages

## Non-Goals (Explicitly Out of Scope)

- ❌ Autonomous agent (no background operation)
- ❌ Web UI or REST API (Python-only)
- ❌ Multi-asset management (USDC only)
- ❌ Multi-chain support (Base only)
- ❌ Advanced strategies (ML, optimization)
- ❌ State persistence (no database)
- ❌ Historical analytics (no logging)
- ❌ Testing suite (focus on working demo)
- ❌ Deployment/hosting (local execution only)

---

**This architecture provides the mechanical foundation for a DeFi agent while remaining simple, clear, and functional.**
