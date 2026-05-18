#!/usr/bin/env python3
"""Display the EVM address for the configured OWS wallet."""

import os
from pathlib import Path

from dotenv import load_dotenv
from ows import get_wallet


DEFAULT_WALLET_NAME = "agent-treasury"


def main():
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)

    wallet_name = os.getenv('OWS_WALLET', DEFAULT_WALLET_NAME)
    vault_path = os.getenv('OWS_VAULT_PATH') or None

    try:
        wallet = get_wallet(wallet_name, vault_path_opt=vault_path)
    except Exception as e:
        print(f"✗ OWS wallet '{wallet_name}' not found: {e}")
        print(f"Run: python3 helpers/create_ows_wallet.py --name {wallet_name}")
        return

    evm_account = next(
        (account for account in wallet['accounts'] if account['chain_id'].startswith('eip155:')),
        None,
    )
    if evm_account is None:
        print(f"✗ OWS wallet '{wallet_name}' has no EVM account")
        return

    print("=" * 70)
    print("OWS WALLET INFORMATION")
    print("=" * 70)
    print(f"\nWallet name: {wallet['name']}")
    print(f"Wallet id:   {wallet['id']}")
    print(f"EVM address: {evm_account['address']}")
    print(f"Vault:       {vault_path or '~/.ows'}")
    print("\nPrivate keys are managed by OWS and are not exposed by this tool.")
    print("=" * 70)


if __name__ == "__main__":
    main()
