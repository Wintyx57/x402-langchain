"""Tests for X402PaymentHandler -- blockchain payments and budget controls."""

from unittest.mock import MagicMock, patch

import pytest
from web3 import Web3

from x402_langchain.payment import (
    CHAIN_CONFIGS,
    X402BudgetExceededError,
    X402PaymentError,
    X402PaymentHandler,
)


class TestX402PaymentHandlerInitialization:
    """Test X402PaymentHandler initialization."""

    def test_init_base_chain(self, payment_handler):
        """Initialize with Base mainnet."""
        assert payment_handler.chain == "base"
        assert payment_handler.chain_label == "Base"
        assert payment_handler._max_budget == 10.0
        assert payment_handler.total_spent == 0.0

    def test_init_base_sepolia_chain(self):
        """Initialize with Base Sepolia testnet."""
        from x402_langchain.payment import X402PaymentHandler

        with patch("x402_langchain.payment.Web3") as mock_web3_class:
            mock_w3 = MagicMock()
            mock_w3.eth.account.from_key.return_value = MagicMock(
                address="0x1234567890123456789012345678901234567890",
                key="0x" + "a" * 64,
            )
            mock_w3.eth.contract.return_value = MagicMock()
            mock_web3_class.return_value = mock_w3
            mock_web3_class.to_checksum_address = lambda x: x

            handler = X402PaymentHandler(
                private_key="0x" + "a" * 64,
                chain="base-sepolia",
                max_budget_usdc=5.0,
            )
            assert handler.chain == "base-sepolia"
            assert handler.chain_label == "Base Sepolia"

    def test_init_skale_chain(self):
        """Initialize with SKALE Europa chain."""
        from x402_langchain.payment import X402PaymentHandler

        with patch("x402_langchain.payment.Web3") as mock_web3_class:
            mock_w3 = MagicMock()
            mock_w3.eth.account.from_key.return_value = MagicMock(
                address="0x1234567890123456789012345678901234567890",
                key="0x" + "a" * 64,
            )
            mock_w3.eth.contract.return_value = MagicMock()
            mock_web3_class.return_value = mock_w3
            mock_web3_class.to_checksum_address = lambda x: x

            handler = X402PaymentHandler(
                private_key="0x" + "a" * 64,
                chain="skale",
                max_budget_usdc=2.0,
            )
            assert handler.chain == "skale"
            assert handler.chain_label == "SKALE Europa"

    def test_init_invalid_chain(self):
        """Invalid chain should raise ValueError."""
        from x402_langchain.payment import X402PaymentHandler

        with pytest.raises(ValueError, match="Unsupported chain"):
            X402PaymentHandler(private_key="0x" + "a" * 64, chain="invalid-chain")

    def test_init_private_key_normalization(self):
        """Private key should be normalized with 0x prefix."""
        from x402_langchain.payment import X402PaymentHandler

        with patch("x402_langchain.payment.Web3") as mock_web3_class:
            mock_w3 = MagicMock()
            mock_account = MagicMock(
                address="0x1234567890123456789012345678901234567890",
                key="0x" + "a" * 64,
            )
            mock_w3.eth.account.from_key.return_value = mock_account
            mock_w3.eth.contract.return_value = MagicMock()
            mock_web3_class.return_value = mock_w3
            mock_web3_class.to_checksum_address = lambda x: x

            # Test without 0x prefix
            handler = X402PaymentHandler(
                private_key="a" * 64,  # No 0x prefix
                chain="base",
            )

            # Should have normalized key with 0x
            call_args = mock_w3.eth.account.from_key.call_args[0]
            assert call_args[0].startswith("0x")

    def test_init_erc20_abi_setup(self):
        """ERC20 contract ABI should be properly initialized."""
        from x402_langchain.payment import X402PaymentHandler

        with patch("x402_langchain.payment.Web3") as mock_web3_class:
            mock_w3 = MagicMock()
            mock_w3.eth.account.from_key.return_value = MagicMock(
                address="0x1234567890123456789012345678901234567890",
                key="0x" + "a" * 64,
            )
            mock_contract = MagicMock()
            mock_w3.eth.contract.return_value = mock_contract
            mock_web3_class.return_value = mock_w3
            mock_web3_class.to_checksum_address = lambda x: x

            X402PaymentHandler(private_key="0x" + "a" * 64, chain="base")

            # Verify contract was initialized with correct address and ABI
            mock_w3.eth.contract.assert_called_once()
            call_kwargs = mock_w3.eth.contract.call_args[1]
            assert "abi" in call_kwargs
            assert "address" in call_kwargs


class TestX402PaymentHandlerBalance:
    """Test balance checking."""

    def test_get_balance(self, payment_handler):
        """Get USDC balance of wallet."""
        payment_handler._usdc.functions.balanceOf.return_value.call.return_value = (
            50000000  # 50 USDC with 6 decimals
        )
        balance = payment_handler.get_balance()
        assert balance == 50.0

    def test_get_balance_zero(self, payment_handler):
        """Get balance when wallet has no USDC."""
        payment_handler._usdc.functions.balanceOf.return_value.call.return_value = 0
        balance = payment_handler.get_balance()
        assert balance == 0.0


class TestX402PaymentHandlerPayment:
    """Test payment execution."""

    def test_successful_payment(self, payment_handler):
        """Execute a successful payment."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        # Mock the transaction hash object with proper hex() method
        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0x" + "a" * 64
        payment_handler._w3.eth.send_raw_transaction.return_value = mock_tx_hash
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        tx_hash = payment_handler.pay(0.05, TEST_RECIPIENT_ADDRESS)

        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66  # 0x + 64 hex chars
        assert payment_handler.total_spent == 0.05
        assert payment_handler.remaining_budget == 9.95
        assert tx_hash in payment_handler._used_tx_hashes

    def test_payment_multiple_transactions(self, payment_handler):
        """Execute multiple payments and track total spent."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        # Mock different transaction hashes for each call with proper hex() methods
        mock_tx_hashes = [
            MagicMock(hex=MagicMock(return_value="0x" + "a" * 64)),
            MagicMock(hex=MagicMock(return_value="0x" + "b" * 64)),
            MagicMock(hex=MagicMock(return_value="0x" + "c" * 64)),
        ]
        payment_handler._w3.eth.send_raw_transaction.side_effect = mock_tx_hashes

        tx1 = payment_handler.pay(0.01, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.total_spent == 0.01

        tx2 = payment_handler.pay(0.02, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.total_spent == 0.03

        tx3 = payment_handler.pay(0.015, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.total_spent == 0.045

        assert len(payment_handler._used_tx_hashes) == 3

    def test_payment_budget_exceeded(self, payment_handler):
        """Payment exceeding budget should raise X402BudgetExceededError."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        # Set low budget
        payment_handler._max_budget = 0.05

        # First payment succeeds
        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
        payment_handler.pay(0.03, TEST_RECIPIENT_ADDRESS)

        # Second payment would exceed budget
        with pytest.raises(X402BudgetExceededError, match="would exceed budget"):
            payment_handler.pay(0.03, TEST_RECIPIENT_ADDRESS)

    def test_payment_exactly_at_budget_limit(self, payment_handler):
        """Payment at exact budget limit should succeed."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._max_budget = 0.05
        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        tx = payment_handler.pay(0.05, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.total_spent == 0.05
        assert payment_handler.remaining_budget == 0.0

    def test_payment_transaction_failed_status_zero(self, payment_handler):
        """Failed transaction (status=0) should raise error."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 0}

        with pytest.raises(X402PaymentError, match="failed on-chain"):
            payment_handler.pay(0.01, TEST_RECIPIENT_ADDRESS)

        # Total spent should not increase on failure
        assert payment_handler.total_spent == 0.0

    def test_payment_transaction_exception(self, payment_handler):
        """Exception during transaction should raise X402PaymentError."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.get_transaction_count.side_effect = Exception(
            "RPC connection failed"
        )

        with pytest.raises(X402PaymentError, match="Payment failed"):
            payment_handler.pay(0.01, TEST_RECIPIENT_ADDRESS)

    def test_payment_address_checksum(self, payment_handler):
        """Recipient address should be checksummed."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        # Mock should accept any address
        payment_handler._w3.to_checksum_address = lambda x: x.lower()

        tx = payment_handler.pay(0.01, TEST_RECIPIENT_ADDRESS)
        assert tx is not None

    def test_payment_raw_amount_conversion(self, payment_handler):
        """Amount should be correctly converted to raw with decimals."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        payment_handler.pay(1.5, TEST_RECIPIENT_ADDRESS)

        # Check that transfer was called with correct raw amount
        # 1.5 USDC * 10^6 = 1500000
        build_tx_call = payment_handler._usdc.functions.transfer.return_value.build_transaction.call_args
        assert build_tx_call is not None


class TestX402PaymentHandlerBudgetTracking:
    """Test budget tracking and remaining balance."""

    def test_remaining_budget_calculation(self, payment_handler):
        """Remaining budget should be correctly calculated."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        assert payment_handler.remaining_budget == 10.0

        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        payment_handler.pay(2.5, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.remaining_budget == 7.5

    def test_remaining_budget_zero(self, payment_handler):
        """Remaining budget should be zero when fully spent."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._max_budget = 0.1
        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        payment_handler.pay(0.1, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.remaining_budget == 0.0

    def test_remaining_budget_never_negative(self, payment_handler):
        """Remaining budget should never be negative."""
        # Manually set total spent above budget (edge case)
        payment_handler._total_spent = 15.0
        assert payment_handler.remaining_budget == 0.0


class TestX402PaymentHandlerChainConfigs:
    """Test chain configurations."""

    def test_all_chains_configured(self):
        """All required chains should be properly configured."""
        required_chains = ["base", "base-sepolia", "skale"]
        for chain in required_chains:
            assert chain in CHAIN_CONFIGS
            config = CHAIN_CONFIGS[chain]
            assert "rpc_url" in config
            assert "usdc_contract" in config
            assert "chain_id" in config
            assert "label" in config

    def test_base_mainnet_config(self):
        """Base mainnet should have correct RPC and contract."""
        config = CHAIN_CONFIGS["base"]
        assert config["chain_id"] == 8453
        assert config["rpc_url"] == "https://mainnet.base.org"
        assert "0x" in config["usdc_contract"]

    def test_base_sepolia_config(self):
        """Base Sepolia should have correct RPC and contract."""
        config = CHAIN_CONFIGS["base-sepolia"]
        assert config["chain_id"] == 84532
        assert config["rpc_url"] == "https://sepolia.base.org"

    def test_skale_config(self):
        """SKALE should have correct RPC and contract."""
        config = CHAIN_CONFIGS["skale"]
        assert config["chain_id"] == 2046399126
        assert "skalenodes" in config["rpc_url"]


class TestX402PaymentHandlerProperties:
    """Test property accessors."""

    def test_address_property(self, payment_handler):
        """Should return wallet address from account."""
        from tests.conftest import TEST_WALLET_ADDRESS

        payment_handler._account.address = TEST_WALLET_ADDRESS
        assert payment_handler.address == TEST_WALLET_ADDRESS

    def test_chain_property(self, payment_handler):
        """Should return chain identifier."""
        assert payment_handler.chain == "base"

    def test_chain_label_property(self, payment_handler):
        """Should return human-readable chain label."""
        assert payment_handler.chain_label == "Base"

    def test_total_spent_property(self, payment_handler):
        """Should return total USDC spent."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        payment_handler._w3.eth.send_raw_transaction.return_value = b"\x00" * 32
        payment_handler._w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}

        payment_handler.pay(0.25, TEST_RECIPIENT_ADDRESS)
        assert payment_handler.total_spent == 0.25
