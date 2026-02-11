"""x402 Payment Handler -- handles USDC payments on Base and SKALE for the x402 protocol."""

from __future__ import annotations

import logging
from typing import Optional

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

logger = logging.getLogger(__name__)

# ERC-20 minimal ABI (transfer + balanceOf + decimals)
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]

# Chain configurations matching the x402 Bazaar backend
CHAIN_CONFIGS = {
    "base": {
        "rpc_url": "https://mainnet.base.org",
        "usdc_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "chain_id": 8453,
        "label": "Base",
    },
    "base-sepolia": {
        "rpc_url": "https://sepolia.base.org",
        "usdc_contract": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "chain_id": 84532,
        "label": "Base Sepolia",
    },
    "skale": {
        "rpc_url": "https://mainnet.skalenodes.com/v1/elated-tan-skat",
        "usdc_contract": "0x5F795bb52dAc3085f578f4877D450e2929D2F13d",
        "chain_id": 2046399126,
        "label": "SKALE Europa",
    },
}

USDC_DECIMALS = 6


class X402PaymentError(Exception):
    """Raised when a payment fails."""


class X402BudgetExceededError(X402PaymentError):
    """Raised when total spending would exceed the configured budget."""


class X402PaymentHandler:
    """Handles USDC payments on Base or SKALE for the x402 protocol.

    Args:
        private_key: Hex-encoded private key (with or without 0x prefix).
        chain: Chain identifier -- "base", "base-sepolia", or "skale".
        max_budget_usdc: Maximum cumulative spend in USDC before refusing further payments.
    """

    def __init__(
        self,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> None:
        if chain not in CHAIN_CONFIGS:
            raise ValueError(
                f"Unsupported chain: {chain}. Choose from: {', '.join(CHAIN_CONFIGS)}"
            )

        self._chain_key = chain
        self._config = CHAIN_CONFIGS[chain]
        self._max_budget = max_budget_usdc
        self._total_spent: float = 0.0
        self._used_tx_hashes: set[str] = set()

        # Normalize private key
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        self._w3 = Web3(Web3.HTTPProvider(self._config["rpc_url"]))
        # POA middleware for Base and SKALE
        self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self._account = self._w3.eth.account.from_key(private_key)
        self._usdc = self._w3.eth.contract(
            address=Web3.to_checksum_address(self._config["usdc_contract"]),
            abi=ERC20_ABI,
        )

        logger.info(
            "X402PaymentHandler initialized on %s (wallet: %s...%s, budget: %.2f USDC)",
            self._config["label"],
            self._account.address[:6],
            self._account.address[-4:],
            self._max_budget,
        )

    @property
    def chain(self) -> str:
        """Current chain identifier."""
        return self._chain_key

    @property
    def chain_label(self) -> str:
        """Human-readable chain label."""
        return self._config["label"]

    @property
    def address(self) -> str:
        """Wallet address."""
        return self._account.address

    @property
    def total_spent(self) -> float:
        """Total USDC spent so far."""
        return self._total_spent

    @property
    def remaining_budget(self) -> float:
        """Remaining USDC budget."""
        return max(0.0, self._max_budget - self._total_spent)

    def get_balance(self) -> float:
        """Get the current USDC balance of the wallet.

        Returns:
            USDC balance as a float.
        """
        raw = self._usdc.functions.balanceOf(self._account.address).call()
        return raw / (10**USDC_DECIMALS)

    def pay(self, amount: float, recipient: str) -> str:
        """Transfer USDC to a recipient on-chain.

        Args:
            amount: Amount in USDC (e.g., 0.05).
            recipient: Recipient wallet address (0x...).

        Returns:
            Transaction hash as a hex string.

        Raises:
            X402BudgetExceededError: If paying would exceed the max budget.
            X402PaymentError: If the transaction fails.
        """
        # Budget check
        if self._total_spent + amount > self._max_budget:
            raise X402BudgetExceededError(
                f"Payment of {amount} USDC would exceed budget. "
                f"Spent: {self._total_spent:.4f}, Budget: {self._max_budget:.2f}, "
                f"Remaining: {self.remaining_budget:.4f}"
            )

        raw_amount = int(amount * (10**USDC_DECIMALS))
        recipient_addr = Web3.to_checksum_address(recipient)

        logger.info(
            "Sending %.4f USDC to %s on %s...",
            amount,
            recipient_addr[:10] + "...",
            self._config["label"],
        )

        try:
            nonce = self._w3.eth.get_transaction_count(self._account.address)

            tx = self._usdc.functions.transfer(
                recipient_addr, raw_amount
            ).build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                    "chainId": self._config["chain_id"],
                    "gas": 100_000,
                    "maxFeePerGas": self._w3.eth.gas_price * 2,
                    "maxPriorityFeePerGas": self._w3.eth.max_priority_fee,
                }
            )

            signed = self._w3.eth.account.sign_transaction(tx, self._account.key)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hex = tx_hash.hex()

            # Wait for confirmation
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt["status"] != 1:
                raise X402PaymentError(
                    f"Transaction {tx_hex} failed on-chain (status=0)"
                )

            # Track spending and used hashes
            self._total_spent += amount
            self._used_tx_hashes.add(tx_hex)

            logger.info(
                "Payment confirmed: %s (%.4f USDC, total spent: %.4f)",
                tx_hex[:18] + "...",
                amount,
                self._total_spent,
            )
            return tx_hex

        except X402PaymentError:
            raise
        except Exception as exc:
            raise X402PaymentError(f"Payment failed: {exc}") from exc
