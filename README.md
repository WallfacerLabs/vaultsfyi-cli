# Agentic DeFi

A DeFi capital management agent-like interactive console that demonstrates the mechanics of autonomous DeFi interactions. Manages USDC on Base network, discovers idle capital, analyzes yield opportunities, and deploys capital to the best available vaults. Built to provide building blocks and insights into how to design and deploy complex fund managements agents. Optimized for AI, no paper agreements or api keys required.

## 🔐 Truly Non-Custodial DeFi, now with OWS

**You own and control everything:**

- ✅ **Your wallet, your crypto** - Key material is managed by Open Wallet Standard in your local OWS vault
- ✅ **No plaintext private keys in `.env`** - The agent never reads or stores raw private keys
- ✅ **Direct on-chain transactions** - No intermediaries or custodians
- ✅ **Direct smart contract interactions** - Transactions are signed by your OWS wallet and broadcast from your machine
- ✅ **You own the LP tokens** - Vault shares go directly to YOUR wallet
- ✅ **Full transparency** - Every transaction is visible on-chain
- ✅ **No middlemen** - Direct interaction with DeFi protocols

This is real DeFi: non-custodial, permissionless, and transparent. OWS only replaces ad-hoc private-key handling with a shared local wallet standard.

## Features

- **Gas Validation**: Checks ETH balance upfront before any transaction
- **Idle Asset Detection**: Discovers USDC sitting idle in your wallet
- **Opportunity Discovery**: Finds best yield opportunities with API-side filtering
- **Smart Diversification**: Automatically avoids vaults with existing positions
- **Position Management**: Track positions with human-readable nicknames
- **Full Redemption Flow**: Redeem partial or full amounts from positions
- **x402 Payment Protocol**: Pay-per-use API access with USDC
- **Open Wallet Standard**: Local wallet storage/signing via OWS instead of repo-specific private-key files

## Installation

1. **Clone the repository**:
```bash
git clone https://github.com/WallfacerLabs/agentic_defi.git
cd agentic_defi
```

2. **Create and activate virtual environment** (REQUIRED):

⚠️ **You MUST create a virtual environment before installing dependencies**

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (run this every time you use the agent)
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

3. **Install dependencies** (make sure venv is activated first):
```bash
pip install -r requirements.txt
```

4. **Install the OWS CLI** (needed for x402-paid requests):
```bash
curl -fsSL https://docs.openwallet.sh/install.sh | bash
ows wallet info
```

The Python package in `requirements.txt` handles OWS wallet lookup and transaction signing. The `ows` CLI handles `ows pay request` when an API endpoint requires x402 payment.

5. **Configure environment**:
```bash
# Copy .env.example to .env
cp .env.example .env
```

Default wallet settings:
```bash
OWS_WALLET=agent-treasury
OWS_CHAIN=base
BASE_RPC_URL=https://mainnet.base.org
```

Optional settings:
```bash
# Use a wallet passphrase or scoped OWS API token when your wallet requires one.
# Prefer exporting this in your shell for real funds instead of committing it to .env.
OWS_PASSPHRASE=your_wallet_passphrase_or_ows_key

# Defaults to ~/.ows if omitted.
OWS_VAULT_PATH=/path/to/ows-vault

# Only needed if `ows` is not on PATH.
OWS_CLI_PATH=/usr/local/bin/ows

# Optional vaults.fyi API key. If omitted, paid endpoints fall back to x402 via OWS.
VAULTS_API_KEY=your_vaults_api_key_here
```

6. **Create or import an OWS wallet**:
```bash
# Make sure your virtual environment is activated, then create a new OWS wallet:
python3 helpers/create_ows_wallet.py --name agent-treasury

# Or import an existing wallet with the OWS CLI:
ows wallet import --name agent-treasury --mnemonic
ows wallet import --name agent-treasury --private-key --chain evm
```

The helper updates `.env` with `OWS_WALLET` and `OWS_CHAIN`. It does **not** print or store plaintext private keys.

7. **View your wallet address**:
```bash
# Make sure your virtual environment is activated, then:
python3 helpers/show_wallet_address.py
```

8. **Fund your wallet**:

Send funds to your OWS wallet address (from step 7):
- **ETH** (for gas fees): `0.002 ETH` (enough for multiple transactions)
- **USDC** (for deposits and x402 payments): `10 USDC` (to test the agent)

You can bridge funds to Base network using:
- [Official Base Bridge](https://bridge.base.org)
- [Relay Bridge](https://relay.link/bridge/base)
- Or send directly from a CEX that supports Base network

9. **Configure settings** (optional):

⚠️ **SKIP THIS ON YOUR FIRST RUN** ⚠️
```
For first-time users: DO NOT modify config.yaml yet!
Run the agent with default settings first to understand how it works.

Only adjust these settings after you've successfully completed at least one full cycle.
```

Advanced users can edit `config.yaml` to adjust:
```bash
# - Minimum APY threshold
# - Minimum TVL threshold
# - Vault whitelist
# - Display settings
```

## Quick Start

**Important**: Make sure your virtual environment is activated before running any commands:
```bash
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

### Basic Usage

```python
from agent import Agent

# Initialize agent
agent = Agent()

# Check current state (gas, USDC, positions)
agent.show_state()

# Check idle USDC
agent.show_idle_assets()

# Deploy 10% of idle USDC to best vault
agent.deploy_capital(10)

# View positions
agent.show_positions()

# Redeem 50% from a position (by nickname)
agent.redeem('YearnUSDCV', 50)

# Redeem everything
agent.redeem_all()
```

### 🚀 Run the Interactive Console (START HERE!)

**This is the core experience - run this to get started:**

```bash
python examples/interactive.py
```

The interactive console will guide you through:
- Checking your wallet balance and gas
- Viewing idle USDC available for deployment
- Discovering the best yield opportunities and deploying capital to vaults
- Managing and redeeming positions

💡 **First-time users**: This is where you should begin!

## Wallet Management

The `helpers/` directory contains utilities for working with your Open Wallet Standard wallet.

**Remember**: Always activate your virtual environment first:
```bash
source venv/bin/activate  # On macOS/Linux
```

### Create New OWS Wallet

```bash
python3 helpers/create_ows_wallet.py --name agent-treasury
```

This script will:
- Check whether the named OWS wallet already exists
- Create a new OWS wallet if needed
- Automatically add `OWS_WALLET` and `OWS_CHAIN` to `.env`
- Display the wallet name, wallet id, and EVM address
- Never display or write a plaintext private key

**Output example**:
```
======================================================================
OWS WALLET READY
======================================================================

Wallet name: agent-treasury
Wallet id:   3198bc9c-...
EVM address: 0xABCDEF1234567890...
Vault:       ~/.ows

.env updated with OWS_WALLET and OWS_CHAIN.

No private key was written to disk by this helper. OWS stores encrypted key material in the local vault.
```

### Import Existing Wallet

Use the OWS CLI if you already have a wallet:

```bash
# Import from mnemonic
ows wallet import --name agent-treasury --mnemonic

# Import an existing EVM private key into the OWS vault
ows wallet import --name agent-treasury --private-key --chain evm
```

Then set:

```bash
OWS_WALLET=agent-treasury
OWS_CHAIN=base
```

### View Wallet Address

```bash
python3 helpers/show_wallet_address.py
```

This script displays the EVM address for the configured OWS wallet. Useful when you need to:
- Find your wallet address to send ETH for gas
- Verify which OWS wallet you're using
- Share your address to receive funds

**Output example**:
```
======================================================================
OWS WALLET INFORMATION
======================================================================

Wallet name: agent-treasury
Wallet id:   3198bc9c-...
EVM address: 0xABCDEF1234567890...
Vault:       ~/.ows

Private keys are managed by OWS and are not exposed by this tool.
======================================================================
```

### Scoped Agent Access

For real funds, prefer an OWS policy plus scoped API token instead of giving the agent your owner passphrase:

```bash
cat > base-policy.json <<'JSON'
{
  "id": "base-only",
  "name": "Base only",
  "version": 1,
  "created_at": "2026-05-18T00:00:00Z",
  "rules": [
    { "type": "allowed_chains", "chain_ids": ["eip155:8453"] }
  ],
  "action": "deny"
}
JSON

ows policy create --file base-policy.json
ows key create --name agentic-defi --wallet agent-treasury --policy base-only
```

Save the returned `ows_key_...` token as `OWS_PASSPHRASE` in your shell or local `.env`.

## Architecture

The agent uses a clean 4-layer architecture:

1. **Orchestration Layer** (`agent.py`)
   - High-level user interface
   - Coordinates between all layers
   - Handles error messages and display

2. **API Layer** (`api/`)
   - x402 payment client
   - Position queries
   - Opportunity discovery
   - Transaction generation

3. **Strategy Layer** (`strategy/`)
   - Vault filtering and selection
   - Diversification logic
   - Whitelist management

4. **Core Layer** (`core/`)
   - OWS wallet lookup
   - Transaction signing through OWS
   - Gas estimation and validation
   - Transaction broadcasting

## Configuration

### config.yaml

```yaml
# Network Configuration
network: base
asset: USDC
asset_address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Investment Rules
investment:
  min_deposit_usd: 0.10  # $0.10 minimum

# Vault Selection Criteria
criteria:
  min_apy: 0.01         # 1% minimum APY
  min_tvl: 1000000      # $1M minimum TVL
  apy_interval: "1day"  # Use 1-day APY

# Display Configuration
display:
  decimals: 2                    # USD decimals
  position_retry_attempts: 3     # Retry after deploy
  position_retry_delay: 5        # Wait 5s between retries

# Vault Whitelist (optional)
vault_whitelist: []  # Empty = allow all vaults
```

### Environment Variables (.env)

```bash
OWS_WALLET=agent-treasury                      # OWS wallet name or UUID
OWS_CHAIN=base                                 # Chain used for OWS signing
OWS_PASSPHRASE=your_passphrase_or_ows_key      # Optional wallet passphrase/scoped OWS token
OWS_VAULT_PATH=/path/to/ows-vault              # Optional, defaults to ~/.ows
OWS_CLI_PATH=/usr/local/bin/ows                # Optional, auto-detected if on PATH
BASE_RPC_URL=https://mainnet.base.org          # Base RPC endpoint
VAULTS_API_KEY=your_vaults_api_key_here        # Optional, otherwise x402 via OWS
```

## Key Requirements Implemented

This implementation addresses key requirements for safe and reliable DeFi interactions:

- **Gas Validation**: Check gas (ETH) upfront before transactions
- **Minimum Deposits**: Minimum deposit amount of $0.10
- **Clear Errors**: Clear error messages for edge cases
- **Position Nicknames**: Human-readable nicknames (first 10 chars of vault name)
- **Simple Redemption**: Single-step redemption only (no multi-step complexity)
- **Clean Display**: Filter zero-balance positions from display
- **Retry Logic**: Retry position display after deployment (3x, 5s delay) to handle indexing delays
- **Multi-Transaction**: Execute multiple transactions (approve + deposit) sequentially
- **Safety**: Never revoke approvals on failure
- **Precision**: Handle floating-point precision for 100% redemptions
- **Formatting**: Display 2 decimal places for USD amounts, 1-day APY everywhere

## API Costs

The agent uses x402 payment protocol for API access when `VAULTS_API_KEY` is not provided or when the API returns `402 Payment Required`. Paid requests are delegated to `ows pay request`, so payment signing happens through OWS rather than plaintext private-key handling.

⚠️ **Note: These are temporary test prices and subject to change** ⚠️

Current test pricing:
- `get_idle_assets()`: ~$0.01 USDC
- `get_positions()`: ~$0.01 USDC
- `get_best_deposit_options()`: ~$0.01 USDC
- `generate_deposit_tx()`: ~$0.01 USDC

A full `deploy_capital()` operation costs approximately **$0.04 USDC** in API payments during testing.

## Safety Features

1. **OWS key management**: No plaintext private key in `.env`; signing happens through Open Wallet Standard
2. **Gas validation**: Checks ETH balance before any transaction
3. **Minimum deposit**: Prevents dust deployments ($0.10 minimum)
4. **Vault whitelist**: Optional restriction to trusted vaults
5. **Automatic diversification**: Never deploys to existing positions
6. **No approval revocation**: If deposit fails, approval stays (user must manually revoke if desired)

## Examples

### Deploy 10% of idle USDC

```python
agent = Agent()
agent.deploy_capital(10)
```

**Output**:
```
=== Deploying 10% of idle capital ===

Checking idle USDC...
Idle USDC: $100.00
Deploy amount: $10.00
Checking existing positions...
Found 0 existing position(s)
Finding best vaults...
Found 15 vault(s)
✓ Selected Yearn USDC Vault with 5.23% APY
Generating transaction(s)...
Generated 2 transaction(s)
Executing transaction(s)...

✓ Deployed $10.00 to Yearn USDC Vault
Transaction 1 (approve): 0x1234...
Transaction 2 (deposit): 0x5678...

Refreshing positions...

=== Current Positions ===

Nickname    Vault Name         Asset  APY        Balance
----------  -----------------  -----  ---------  --------
YearnUSDCV  Yearn USDC Vault   USDC   5.23% (1d) $10.00

Total: $10.00
```

### View Positions

```python
agent = Agent()
agent.show_positions()
```

### Redeem by Nickname

```python
agent = Agent()
agent.redeem('YearnUSDCV', 50)  # Redeem 50%
```

## Documentation

- [architecture.md](architecture.md) - Detailed architecture documentation with design decisions and rationale

## Notes

- This is a **demonstrative tool**, not an autonomous agent
- User explicitly calls each method
- No background operation or scheduling
- Designed for Base network and USDC only
- Stateless design (queries fresh state each time)

## License

MIT

---

**Built with Claude Code** 🤖
