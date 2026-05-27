"""
x402 / vaults.fyi API client.

Private-key based x402 signing has been removed. Paid requests are delegated to
an Open Wallet Standard-compatible `ows pay request` command when available.
Plain HTTP is still used for endpoints that do not require payment.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from agent.api.query import query_params


class X402Client:
    """Client for making vaults.fyi API requests with OWS-backed payments."""

    def __init__(self, wallet=None, base_url: str = "https://api.vaults.fyi"):
        """Initialize x402 client."""
        load_dotenv(Path.cwd() / ".env", override=False)
        self.wallet = wallet
        self.base_url = base_url.rstrip('/')
        self.ows_cli = os.getenv('OWS_CLI_PATH') or shutil.which('ows')
        self.api_key = os.getenv('VAULTS_API_KEY')

    def make_request(self, endpoint: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict:
        """
        Make an API request.

        Flow:
        1. Send direct GET. If the endpoint is free, return the response.
        2. If the endpoint requires x402 payment, retry via OWS CLI so payment
           signing happens inside the OWS access layer, not inside this process.
        """
        url = f"{self.base_url}{endpoint}"
        params = query_params(params or {})

        headers = {
            'x-402-auth': 'true',
            'Accept': 'application/json'
        }
        if self.api_key:
            headers['x-api-key'] = self.api_key

        response = requests.get(url, params=params, headers=headers, timeout=timeout)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 402:
            return self._make_paid_request(url, params=params, timeout=timeout)

        raise RuntimeError(f"API request failed: {response.status_code} {self._error_message(response)}")

    def _make_paid_request(self, url: str, params: dict[str, Any] | None = None, timeout: int = 60) -> dict:
        """Use `ows pay request` for x402-paid requests."""
        params = query_params(params or {})
        if not self.ows_cli:
            raise RuntimeError(
                "This endpoint requires x402 payment, but the OWS CLI was not found. "
                "Install it with `curl -fsSL https://docs.openwallet.sh/install.sh | bash` "
                "or set OWS_CLI_PATH. The Python agent will not handle plaintext private keys."
            )
        if self.wallet is None:
            from agent.core.wallet import Wallet

            self.wallet = Wallet()

        if params:
            separator = '&' if '?' in url else '?'
            url = f"{url}{separator}{urlencode(params, doseq=True)}"

        command = [
            self.ows_cli,
            'pay',
            'request',
            url,
            '--wallet',
            self.wallet.name,
            '--method',
            'GET',
        ]

        env = os.environ.copy()
        if self.wallet.passphrase is not None:
            env['OWS_PASSPHRASE'] = self.wallet.passphrase
        else:
            command.append('--no-passphrase')

        result = subprocess.run(
            command,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"OWS paid request failed: {stderr}")

        body = result.stdout.strip()
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OWS paid request did not return JSON: {body[:500]}") from exc

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text
        if isinstance(body, dict):
            parts = [str(body.get(key)) for key in ("error", "message", "errorId") if body.get(key)]
            return " ".join(parts) or json.dumps(body)
        return json.dumps(body)
