"""
Main Agent class - orchestration layer.

The Agent remains importable for Python users while the vaultsfyi CLI uses the
same methods underneath.
"""

import time
from typing import List

import yaml

from .api import OpportunityAPI, PositionAPI, TransactionAPI, X402Client
from .core import TransactionExecutor, Wallet
from .strategy import VaultCriteria, VaultSelector


def format_usd(amount: float, decimals: int = 2) -> str:
    """Format USD amount (requirement Q26)."""
    return f"${amount:.{decimals}f}"


def format_apy(apy: float) -> str:
    """Format APY as percentage."""
    return f"{apy * 100:.2f}%"


class Agent:
    """DeFi capital management agent."""

    def __init__(self, config_path: str | None = None, config: dict | None = None):
        """Initialize agent with configuration dict, YAML path, or CLI defaults."""
        if config is not None:
            self.config = config
        elif config_path is not None:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            from .cli.config import agent_config, load_config

            self.config = agent_config(load_config())

        self.wallet = Wallet()
        self.executor = TransactionExecutor(self.wallet)

        api_url = self.config.get("vaults_api_url", "https://api.vaults.fyi")
        self.x402_client = X402Client(self.wallet, api_url)
        self.position_api = PositionAPI(self.x402_client)
        self.opportunity_api = OpportunityAPI(self.x402_client)
        self.transaction_api = TransactionAPI(self.x402_client)

        self.criteria = VaultCriteria(self.config)
        self.selector = VaultSelector(self.criteria)

        self.asset_address = self.config["asset_address"]
        self.network = self.config["network"]
        self.min_deposit_usd = self.config["investment"]["min_deposit_usd"]
        self.display_decimals = self.config["display"]["decimals"]
        self.retry_attempts = self.config["display"]["position_retry_attempts"]
        self.retry_delay = self.config["display"]["position_retry_delay"]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Data-returning methods used by the CLI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_idle_assets(self) -> dict:
        """Return idle USDC balance info."""
        return self.position_api.get_idle_assets(self.wallet.address)

    def get_positions(self) -> List[dict]:
        """Return active positions."""
        return self.position_api.get_positions(self.wallet.address)

    def get_opportunities(self) -> List[dict]:
        """Return filtered deposit opportunities."""
        return self.opportunity_api.get_best_deposit_options(
            self.wallet.address,
            self.config["criteria"],
        )

    def get_state(self) -> dict:
        """Return gas, idle asset, and position summary."""
        gas_info = self.executor.check_gas_balance()
        idle_info = self.get_idle_assets()
        positions = self.get_positions()
        return {
            "wallet": self.wallet.address,
            "network": self.network,
            "asset": self.config.get("asset", "USDC"),
            "gas": gas_info,
            "idle_assets": idle_info,
            "positions_count": len(positions),
        }

    def prepare_deploy(self, percentage: float) -> dict:
        """Validate and build a deployment plan without broadcasting."""
        is_sufficient, error_msg = self.executor.validate_gas_balance()
        if not is_sufficient:
            raise ValueError(error_msg)

        idle_info = self.get_idle_assets()
        idle_usdc = idle_info["usdc_balance"]
        idle_tokens = idle_info["balance_tokens"]
        deploy_amount_usd = idle_usdc * (percentage / 100)
        deploy_amount_tokens = idle_tokens * (percentage / 100)

        if deploy_amount_usd < self.min_deposit_usd:
            raise ValueError(
                f"Deposit amount {format_usd(deploy_amount_usd, self.display_decimals)} "
                f"below minimum {format_usd(self.min_deposit_usd, self.display_decimals)}"
            )

        positions = self.get_positions()
        opportunities = self.get_opportunities()
        selected_vault, reason = self.selector.select_vault(opportunities, positions)
        if selected_vault is None:
            raise ValueError(reason)

        transactions = self.transaction_api.generate_deposit_tx(
            self.wallet.address,
            selected_vault["vault_address"],
            deploy_amount_tokens,
            self.asset_address,
            self.network,
        )

        from .utils import increase_approval_buffer

        transactions = increase_approval_buffer(transactions, buffer_percent=10.0)

        return {
            "action": "deploy",
            "wallet": self.wallet.address,
            "percentage": percentage,
            "idle_usdc": idle_usdc,
            "amount_usd": deploy_amount_usd,
            "amount_tokens": deploy_amount_tokens,
            "vault": selected_vault,
            "reason": reason,
            "transactions": transactions,
            "transaction_count": len(transactions),
            "existing_positions_count": len(positions),
            "opportunities_count": len(opportunities),
        }

    def _asset_tokens_for_usd(self, amount_usd: float, idle_info: dict) -> float:
        idle_usd = float(idle_info.get("usdc_balance", 0))
        idle_tokens = float(idle_info.get("balance_tokens", 0))
        if idle_usd > 0 and idle_tokens > 0:
            return amount_usd * (idle_tokens / idle_usd)
        return amount_usd

    def prepare_deploy_to_vault(
        self,
        vault_address: str,
        amount_usd: float,
        *,
        available_usd: float | None = None,
        amount_tokens: float | None = None,
    ) -> dict:
        """Build a deployment plan to a specific validated vault address."""
        is_sufficient, error_msg = self.executor.validate_gas_balance()
        if not is_sufficient:
            raise ValueError(error_msg)

        idle_info = self.get_idle_assets()
        idle_usdc = float(idle_info["usdc_balance"])
        available_balance = idle_usdc if available_usd is None else float(available_usd)
        available_label = "idle balance" if available_usd is None else "projected available balance"
        if amount_usd > available_balance:
            raise ValueError(
                f"Deploy amount {format_usd(amount_usd)} exceeds "
                f"{available_label} {format_usd(available_balance)}"
            )
        if amount_usd < self.min_deposit_usd:
            raise ValueError(
                f"Deposit amount {format_usd(amount_usd, self.display_decimals)} "
                f"below minimum {format_usd(self.min_deposit_usd, self.display_decimals)}"
            )

        opportunities = self.get_opportunities()
        selected_vault = next((v for v in opportunities if v["vault_address"].lower() == vault_address.lower()), None)
        if selected_vault is None:
            raise ValueError(f"Vault {vault_address} is not in the current eligible opportunity set")

        deploy_amount_tokens = amount_tokens
        if deploy_amount_tokens is None:
            deploy_amount_tokens = self._asset_tokens_for_usd(amount_usd, idle_info)

        transactions = self.transaction_api.generate_deposit_tx(
            self.wallet.address,
            selected_vault["vault_address"],
            deploy_amount_tokens,
            self.asset_address,
            self.network,
        )

        from .utils import increase_approval_buffer

        transactions = increase_approval_buffer(transactions, buffer_percent=10.0)
        return {
            "action": "deploy_idle",
            "wallet": self.wallet.address,
            "amount_usd": amount_usd,
            "amount_tokens": deploy_amount_tokens,
            "vault": selected_vault,
            "reason": f"Deploying to validated target {selected_vault['vault_name']}",
            "transactions": transactions,
            "transaction_count": len(transactions),
        }

    def execute_deploy_plan(self, plan: dict) -> dict:
        """Broadcast a prepared deployment plan."""
        tx_hashes = self.executor.execute_multiple(plan["transactions"])
        return {**plan, "tx_hashes": tx_hashes, "status": "submitted"}

    def prepare_redeem(self, position_nickname: str, percentage: float = 100.0) -> dict:
        """Validate and build a redemption plan without broadcasting."""
        is_sufficient, error_msg = self.executor.validate_gas_balance()
        if not is_sufficient:
            raise ValueError(error_msg)

        positions = self.get_positions()
        position = next((p for p in positions if p["nickname"] == position_nickname), None)
        if position is None:
            available = ", ".join(p["nickname"] for p in positions) or "none"
            raise ValueError(f"Position '{position_nickname}' not found. Available positions: {available}")

        redeem_lp_tokens = position["balance_lp_tokens"] * (percentage / 100)
        redeem_amount_usd = position["balance_usd"] * (percentage / 100)
        is_full_redemption = percentage >= 99.99

        transactions = self.transaction_api.generate_redeem_tx(
            self.wallet.address,
            position["vault_address"],
            redeem_lp_tokens,
            position["lp_decimals"],
            self.asset_address,
            self.network,
            is_full_redemption=is_full_redemption,
        )

        return {
            "action": "redeem",
            "wallet": self.wallet.address,
            "percentage": percentage,
            "position": position,
            "amount_usd": redeem_amount_usd,
            "lp_tokens": redeem_lp_tokens,
            "transactions": transactions,
            "transaction_count": len(transactions),
        }

    def prepare_redeem_by_vault(self, vault_address: str, amount_usd: float | None = None, percentage: float | None = None) -> dict:
        """Build a redemption plan for a specific position vault address."""
        positions = self.get_positions()
        position = next((p for p in positions if p["vault_address"].lower() == vault_address.lower()), None)
        if position is None:
            raise ValueError(f"Position vault '{vault_address}' not found")

        if amount_usd is not None:
            if amount_usd > position["balance_usd"]:
                raise ValueError(f"Redeem amount {format_usd(amount_usd)} exceeds position balance {format_usd(position['balance_usd'])}")
            percentage = (amount_usd / position["balance_usd"]) * 100 if position["balance_usd"] else 0
        percentage = 100.0 if percentage is None else percentage
        return self.prepare_redeem(position["nickname"], percentage)

    def execute_redeem_plan(self, plan: dict) -> dict:
        """Broadcast a prepared redemption plan."""
        transactions = plan["transactions"]
        if len(transactions) == 1:
            tx_hashes = [self.executor.execute(transactions[0])]
        else:
            tx_hashes = self.executor.execute_multiple(transactions)
        return {**plan, "tx_hashes": tx_hashes, "status": "submitted"}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Existing print-oriented Python API
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def show_state(self):
        """Display current state: gas, USDC balance, positions."""
        from .display import format_state_summary

        state = self.get_state()
        print(format_state_summary(
            state["gas"]["balance_eth"],
            state["idle_assets"]["usdc_balance"],
            state["positions_count"],
        ))
        print()

    def show_idle_assets(self):
        """Display idle USDC balance."""
        print("\n=== Idle Assets ===\n")
        idle_info = self.get_idle_assets()
        print(f"Idle USDC: {format_usd(idle_info['usdc_balance'], self.display_decimals)}")
        print()

    def show_positions(self, retry: bool = False):
        """Display current positions."""
        from .display import format_positions_table

        positions = self.get_positions()
        if not positions:
            if retry:
                print("  No positions found yet (may be indexing delay)...")
            else:
                print("  No active positions")
            return

        print(format_positions_table(positions, self.display_decimals))
        print()

    def deploy_capital(self, percentage: float):
        """Deploy X% of idle capital to best vault."""
        print(f"\n=== Deploying {percentage}% of idle capital ===\n")
        try:
            print("Checking idle USDC...")
            plan = self.prepare_deploy(percentage)
            print(f"Idle USDC: {format_usd(plan['idle_usdc'], self.display_decimals)}")
            print(f"Deploy amount: {format_usd(plan['amount_usd'], self.display_decimals)}")
            print(f"Found {plan['existing_positions_count']} existing position(s)")
            print(f"Found {plan['opportunities_count']} vault(s)")
            print(f"✓ {plan['reason']}")
            print(f"Generated {plan['transaction_count']} transaction(s)")
            print("Executing transaction(s)...")
            result = self.execute_deploy_plan(plan)
        except Exception as e:
            from .display import format_error

            print(format_error(f"Transaction failed: {str(e)}"))
            return

        from .display import format_deploy_success

        print(format_deploy_success(
            result["amount_usd"],
            result["vault"]["vault_name"],
            result["tx_hashes"],
            self.display_decimals,
        ))
        print("\nRefreshing positions...")
        self._show_positions_with_retry()

    def _show_positions_with_retry(self):
        """Show positions with retry logic."""
        for attempt in range(1, self.retry_attempts + 1):
            positions = self.get_positions()
            if positions:
                self.show_positions()
                return
            if attempt < self.retry_attempts:
                print(f"Attempt {attempt}/{self.retry_attempts}: No positions yet, retrying in {self.retry_delay}s...")
                time.sleep(self.retry_delay)
            else:
                print(f"Position not showing after {self.retry_attempts} attempts (may take longer to index)\n")

    def redeem(self, position_nickname: str, percentage: float = 100.0):
        """Redeem from position by nickname."""
        print(f"\n=== Redeeming {percentage}% from {position_nickname} ===\n")
        try:
            print("Finding position...")
            plan = self.prepare_redeem(position_nickname, percentage)
            position = plan["position"]
            print(f"Found: {position['vault_name']}")
            print(
                f"Redeem amount: {format_usd(plan['amount_usd'], self.display_decimals)} "
                f"({plan['lp_tokens']:.6f} LP tokens)"
            )
            print("Generating redemption transaction...")
            print("Executing transaction(s)...")
            result = self.execute_redeem_plan(plan)
        except Exception as e:
            from .display import format_error

            print(format_error(f"Transaction failed: {str(e)}"))
            return

        from .display import format_redeem_success

        tx_hashes = result["tx_hashes"]
        print(format_redeem_success(result["amount_usd"], result["position"]["vault_name"], tx_hashes[0], self.display_decimals))
        for i, tx_hash in enumerate(tx_hashes[1:], start=2):
            print(f"  Transaction {i}: {tx_hash}")
        print()
        self.show_positions()

    def redeem_all(self):
        """Redeem 100% from all positions."""
        print("\n=== Redeeming all positions ===\n")
        positions = self.get_positions()
        if not positions:
            print("No positions to redeem\n")
            return
        print(f"Found {len(positions)} position(s) to redeem\n")
        for i, position in enumerate(positions, 1):
            print(f"[{i}/{len(positions)}] Redeeming from {position['vault_name']}...")
            self.redeem(position["nickname"], 100.0)
            print()
        print("✓ All positions redeemed\n")

    def help(self):
        """Display help information with available commands."""
        from .display import command_list, section_header, subsection_header, tip_box

        print(section_header("DeFi Agent Help"))
        commands = [
            ("agent.show_state()", "Display gas balance, USDC balance, and position count"),
            ("agent.show_positions()", "Show detailed position table with APY and balances"),
            ("agent.show_idle_assets()", "Show idle USDC available for deployment"),
            ("agent.deploy_capital(percentage)", "Deploy % of idle USDC to highest yield vault"),
            ("agent.redeem(nickname, percentage)", "Redeem % from specific position by nickname"),
            ("agent.redeem_all()", "Redeem 100% from all active positions"),
            ("agent.help()", "Show this help message"),
        ]
        print(command_list(commands))
        print("\n" + subsection_header("Examples"))
        for example in [
            "agent.deploy_capital(10)        # Deploy 10% of idle USDC",
            "agent.redeem('SparkUSDCV', 50)  # Redeem 50% from SparkUSDCV",
            "agent.show_positions()          # Refresh position view",
        ]:
            print(f"  {example}")
        print()
        tips = [
            "Nicknames are first 10 chars of vault name (spaces removed)",
            "Minimum deposit: $0.10 USDC",
            "All transactions require gas (ETH)",
            "Positions may take 5-10 seconds to update after transactions",
        ]
        print(tip_box(tips))
        print()
