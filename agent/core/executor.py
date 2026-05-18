"""
Transaction execution module.

Transactions are built locally, signed through Open Wallet Standard, then
broadcast via the configured Base RPC. The agent never reads plaintext private
keys.
"""

import rlp
import time
import os
from typing import List, Tuple

from dotenv import load_dotenv
from eth_account._utils.legacy_transactions import (
    encode_transaction,
    serializable_unsigned_transaction_from_dict,
)
from web3 import Web3

from .wallet import Wallet


class TransactionExecutor:
    """Executes blockchain transactions through an OWS-backed wallet."""

    def __init__(self, wallet: Wallet, rpc_url: str = None):
        """Initialize executor with wallet and RPC connection."""
        self.wallet = wallet

        if rpc_url is None:
            load_dotenv()
            rpc_url = os.getenv('BASE_RPC_URL', 'https://mainnet.base.org')

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {rpc_url}")

    def check_gas_balance(self) -> dict:
        """
        Check ETH balance for gas (requirement Q1).
        Returns dict with balance info and sufficiency check.
        """
        balance_wei = self.w3.eth.get_balance(self.wallet.address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')

        min_gas_eth = 0.001
        sufficient = balance_eth >= min_gas_eth

        return {
            'balance_wei': balance_wei,
            'balance_eth': float(balance_eth),
            'sufficient': sufficient,
            'min_required_eth': min_gas_eth
        }

    def validate_gas_balance(self) -> Tuple[bool, str]:
        """
        Validate sufficient gas balance.
        Returns (is_sufficient, error_message).
        """
        gas_info = self.check_gas_balance()

        if not gas_info['sufficient']:
            error = (
                f"Insufficient ETH for gas. "
                f"Have {gas_info['balance_eth']:.6f} ETH, "
                f"need at least {gas_info['min_required_eth']:.6f} ETH."
            )
            return False, error

        return True, ""

    def _serialize_unsigned_transaction(self, transaction: dict) -> str:
        """Return OWS-compatible unsigned legacy transaction bytes as hex."""
        unsigned = serializable_unsigned_transaction_from_dict(transaction)
        return '0x' + rlp.encode(unsigned).hex()

    def _sign_with_ows(self, transaction: dict) -> bytes:
        """Sign transaction via OWS and assemble a raw EVM transaction."""
        from ows import sign_transaction

        unsigned = serializable_unsigned_transaction_from_dict(transaction)
        unsigned_hex = '0x' + rlp.encode(unsigned).hex()

        result = sign_transaction(
            self.wallet.name,
            self.wallet.chain,
            unsigned_hex,
            passphrase=self.wallet.passphrase,
            vault_path_opt=self.wallet.vault_path,
        )

        signature = result['signature'].removeprefix('0x')
        # OWS returns r||s on some versions and r||s||recovery_id on others.
        # We use the structured recovery_id field for v and ignore the appended byte.
        if len(signature) == 130:
            signature = signature[:128]
        if len(signature) != 128:
            raise ValueError(f"Unexpected OWS EVM signature length: {len(signature)} hex chars")

        r = int(signature[:64], 16)
        s = int(signature[64:], 16)
        recovery_id = int(result.get('recovery_id') or 0)
        v = recovery_id + 35 + (2 * int(transaction['chainId']))

        return encode_transaction(unsigned, vrs=(v, r, s))

    def execute(self, tx_payload: dict, wait_for_confirmation: bool = True, use_pending_nonce: bool = False) -> str:
        """
        Execute a single transaction and return transaction hash.

        Args:
            tx_payload: Transaction data (to, data, value)
            wait_for_confirmation: Wait for transaction to be mined
            use_pending_nonce: Use 'pending' block for nonce (for sequential transactions)
        """
        nonce_block = 'pending' if use_pending_nonce else 'latest'
        nonce = self.w3.eth.get_transaction_count(self.wallet.address, nonce_block)

        transaction = {
            'from': self.wallet.address,
            'to': tx_payload['to'],
            'data': tx_payload['data'],
            'value': int(tx_payload.get('value', 0)),
            'nonce': nonce,
            'chainId': self.w3.eth.chain_id,
        }

        try:
            gas_estimate = self.w3.eth.estimate_gas(transaction)
            transaction['gas'] = int(gas_estimate * 1.5)
        except Exception as e:
            raise Exception(f"Gas estimation failed: {str(e)}")

        transaction['gasPrice'] = self.w3.eth.gas_price

        signed_tx = self._sign_with_ows(transaction)

        tx_hash = self.w3.eth.send_raw_transaction(signed_tx)
        tx_hash_hex = tx_hash.hex()

        if wait_for_confirmation:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt['status'] != 1:
                raise Exception(f"Transaction failed: {tx_hash_hex}")

        return tx_hash_hex

    def execute_multiple(self, tx_payloads: List[dict]) -> List[str]:
        """
        Execute multiple transactions sequentially (requirement Q23).
        Returns list of transaction hashes.
        Never revokes approvals on failure (requirement Q24).
        """
        tx_hashes = []

        for i, tx_payload in enumerate(tx_payloads):
            try:
                use_pending = i > 0
                tx_hash = self.execute(tx_payload, wait_for_confirmation=True, use_pending_nonce=use_pending)
                tx_hashes.append(tx_hash)

                if i < len(tx_payloads) - 1:
                    time.sleep(3)

            except Exception as e:
                if i > 0:
                    raise Exception(
                        f"Transaction {i+1} failed after {i} successful transaction(s). "
                        f"Previous transactions: {tx_hashes}. "
                        f"Error: {str(e)}"
                    )
                else:
                    raise Exception(f"Transaction {i+1} failed: {str(e)}")

        return tx_hashes
