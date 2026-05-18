# Agentic DeFi

A DeFi capital management interactive console for USDC on Base. It discovers idle capital, analyzes yield opportunities, generates vault transactions through vaults.fyi, and executes them from your own wallet.

## Open Wallet Standard, not plaintext keys

This branch uses [Open Wallet Standard](https://openwallet.sh/) for all wallet custody and signing.

- ✅ No `PRIVATE_KEY` in `.env`
- ✅ Keys live in the local OWS vault, normally `~/.ows/`
- ✅ The agent only knows the wallet name and public address
- ✅ Transactions are signed through the OWS signing interface
- ✅ x402-paid API calls are delegated to `ows pay request` when payment is required

This is still self-custody. The important change is that the Python agent no longer owns private-key management. Good. That was a footgun wearing a tutorial hat.

## Features

- **OWS wallet integration**: local encrypted wallet storage and OWS signing
- **Gas validation**: checks ETH balance upfront before any transaction
- **Idle asset detection**: discovers USDC sitting idle in your wallet
- **Opportunity discovery**: finds best yield opportunities with API-side filtering
- **Smart diversification**: avoids vaults with existing positions
- **Position management**: tracks positions with human-readable nicknames
- **Full redemption flow**: redeem partial or full amounts from positions
- **x402 Payment Protocol**: paid API requests through OWS CLI

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/WallfacerLabS/AGENTIC_defi.git
cd AGENTIC_defi
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the OWS CLI for x402-paid requests

The Python SDK is enough for local wallet lookup and transaction signing. The OWS CLI is required when a vaults.fyi endpoint returns `402 Payment Required`.

```bash
curl -fsSL https://docs.openwallet.sh/install.sh | bash
ows wallet info
```

If `ows` is not on `PATH`, set `OWS_CLI_PATH` in `.env`.

### 5. Configure environment

```bash
cp .env.example .env
```

Default `.env` values:

```bash
OWS_WALLET=agent-treasury
OWS_CHAIN=base
BASE_RPC_URL=https://mainnet.base.org
```

Optional values:

```bash
OWS_PASSPHRASE=your_wallet_passphrase_or_scoped_ows_api_token
OWS_VAULT_PATH=/custom/ows/vault
OWS_CLI_PATH=/path/to/ows
```

### 6. Create or import an OWS wallet

Create a fresh local OWS wallet:

```bash
python3 helpers/create_ows_wallet.py --name agent-treasury
```

Use a passphrase-protected wallet:

```bash
python3 helpers/create_ows_wallet.py --name agent-treasury --passphrase 'use-a-real-passphrase'
# Then export OWS_PASSPHRASE in your shell or put it in .env for local testing.
```

Import an existing wallet with the OWS CLI instead:

```bash
# From mnemonic
ows wallet import --name agent-treasury --mnemonic

# From an existing EVM private key, entered through stdin or OWS_PRIVATE_KEY
ows wallet import --name agent-treasury --private-key --chain evm
```

Then make sure `.env` points at it:

```bash
OWS_WALLET=agent-treasury
OWS_CHAIN=base
```

### 7. View your wallet address

```bash
python3 helpers/show_wallet_address.py
```

### 8. Fund your wallet on Base

Send funds to the EVM address from the previous step:

- **ETH** for gas: about `0.002 ETH`
- **USDC** for deposits and x402 API payments: start small, e.g. `10 USDC`

Bridge options:

- [Official Base Bridge](https://bridge.base.org)
- [Relay Bridge](https://relay.link/bridge/base)
- A CEX that supports Base withdrawals

## Quick Start

Activate your venv first:

```bash
source venv/bin/activate
```

Run the interactive console:

```bash
python examples/interactive.py
```

Or use it from Python:

```python
from agent import Agent

agent = Agent()
agent.show_state()
agent.show_idle_assets()
agent.deploy_capital(10)
agent.show_positions()
agent.redeem('YearnUSDCV', 50)
agent.redeem_all()
```

## Wallet Management

### Create a wallet

```bash
python3 helpers/create_ows_wallet.py --name agent-treasury
```

This helper:

- Creates an OWS wallet if it does not exist
- Updates `.env` with `OWS_WALLET` and `OWS_CHAIN`
- Prints the EVM address
- Does **not** print or store a plaintext private key

### Show wallet address

```bash
python3 helpers/show_wallet_address.py
```

This reads the configured OWS wallet and displays its EVM address.

### Scoped agent access

OWS supports scoped API keys and policies. Example:

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

Save the returned `ows_key_...` token as `OWS_PASSPHRASE`. Agents get signing access without ever receiving the underlying key.

## Architecture

The agent uses a 4-layer architecture:

1. **Orchestration Layer** (`agent.py`): high-level user interface and workflows
2. **API Layer** (`api/`): vaults.fyi requests and x402-paid calls via OWS CLI
3. **Strategy Layer** (`strategy/`): vault filtering and selection
4. **Core Layer** (`core/`): OWS wallet lookup, transaction signing, gas estimation, broadcasting

Core signing flow:

1. Build a transaction from the vaults.fyi transaction payload
2. Estimate gas through Base RPC
3. Serialize the unsigned EVM transaction
4. Ask OWS to sign it with `sign_transaction(wallet, chain, tx_hex)`
5. Assemble the signed raw transaction
6. Broadcast via `eth_sendRawTransaction`

## Configuration

### `config.yaml`

```yaml
network: base
asset: USDC
asset_address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

investment:
  min_deposit_usd: 0.10

criteria:
  min_apy: 0.01
  min_tvl: 1000000
  apy_interval: "1day"

display:
  decimals: 2
  position_retry_attempts: 3
  position_retry_delay: 5

vault_whitelist: []
```

### `.env`

```bash
OWS_WALLET=agent-treasury                  # OWS wallet name or UUID
OWS_CHAIN=base                             # OWS chain alias for signing
OWS_PASSPHRASE=ows_key_or_passphrase       # Optional, use shell export for real funds
OWS_VAULT_PATH=/custom/ows/vault           # Optional, defaults to ~/.ows
OWS_CLI_PATH=/usr/local/bin/ows            # Optional, auto-detected if on PATH
BASE_RPC_URL=https://mainnet.base.org      # Base RPC endpoint
```

Do not add `PRIVATE_KEY`. It is intentionally unsupported.

## API Costs

The agent uses x402 payment protocol for paid vaults.fyi API access. If an endpoint returns `402 Payment Required`, `agent/api/client.py` shells out to:

```bash
ows pay request <url> --wallet <OWS_WALLET> --method GET
```

Current test pricing may vary, but expect roughly `$0.01 USDC` per paid API call.

## Safety Features

1. **No plaintext key management**: OWS owns wallet storage and signing
2. **Gas validation**: checks ETH before transactions
3. **Minimum deposit**: prevents dust deployments
4. **Vault whitelist**: optional restriction to trusted vaults
5. **Automatic diversification**: avoids deploying to an existing position
6. **No approval revocation**: if deposit fails, approval remains for manual review

## Notes

- Demonstrative tool, not a background autonomous agent
- User explicitly calls each method
- Base + USDC focused
- Stateless design: queries fresh state each time
- For real funds, prefer a passphrase-protected OWS wallet plus scoped OWS API token

## Documentation

- [architecture.md](architecture.md) - Detailed architecture documentation
- [Open Wallet Standard](https://openwallet.sh/)
- [OWS Python SDK](https://github.com/open-wallet-standard/core/blob/main/docs/sdk-python.md)
- [OWS CLI](https://github.com/open-wallet-standard/core/blob/main/docs/sdk-cli.md)

## License

MIT
