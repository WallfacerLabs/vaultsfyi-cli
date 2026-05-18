#!/usr/bin/env python3
"""Create an Open Wallet Standard wallet for the agent."""

import argparse
from pathlib import Path

from ows import create_wallet, get_wallet


DEFAULT_WALLET_NAME = "agent-treasury"


def update_env(env_path: Path, wallet_name: str, vault_path: str | None):
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    values = {
        "OWS_WALLET": wallet_name,
        "OWS_CHAIN": "base",
    }
    if vault_path:
        values["OWS_VAULT_PATH"] = vault_path

    seen = set()
    next_lines = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in values:
            next_lines.append(f"{key}={values[key]}")
            seen.add(key)
        elif key == "PRIVATE_KEY":
            continue
        else:
            next_lines.append(line)

    if next_lines and next_lines[-1].strip():
        next_lines.append("")

    for key, value in values.items():
        if key not in seen:
            next_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(next_lines).rstrip() + "\n")


def main():
    parser = argparse.ArgumentParser(description="Create an OWS wallet for Agentic DeFi")
    parser.add_argument("--name", default=DEFAULT_WALLET_NAME, help="OWS wallet name")
    parser.add_argument("--passphrase", default=None, help="Optional OWS wallet passphrase")
    parser.add_argument("--words", type=int, choices=[12, 24], default=12, help="Mnemonic word count")
    parser.add_argument("--vault-path", default=None, help="Optional custom OWS vault path")
    parser.add_argument("--env", default=".env", help="Path to .env file to update")
    args = parser.parse_args()

    try:
        wallet = get_wallet(args.name, vault_path_opt=args.vault_path)
        created = False
    except Exception:
        wallet = create_wallet(
            args.name,
            passphrase=args.passphrase,
            words=args.words,
            vault_path_opt=args.vault_path,
        )
        created = True

    update_env(Path(args.env), args.name, args.vault_path)

    evm_account = next(
        account for account in wallet["accounts"]
        if account["chain_id"].startswith("eip155:")
    )

    print("=" * 70)
    print("OWS WALLET READY" if created else "OWS WALLET ALREADY EXISTS")
    print("=" * 70)
    print(f"\nWallet name: {wallet['name']}")
    print(f"Wallet id:   {wallet['id']}")
    print(f"EVM address: {evm_account['address']}")
    print(f"Vault:       {args.vault_path or '~/.ows'}")
    print("\n.env updated with OWS_WALLET and OWS_CHAIN.")
    print("\nNo private key was written to disk by this helper. OWS stores encrypted key material in the local vault.")


if __name__ == "__main__":
    main()
