"""Shared pytest fixtures and mock responses for x402-langchain tests."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest


# Test private key (NOT A REAL KEY - for testing only)
TEST_PRIVATE_KEY = "0x" + "a" * 64

# Test addresses
TEST_WALLET_ADDRESS = "0x1234567890123456789012345678901234567890"
TEST_RECIPIENT_ADDRESS = "0x0987654321098765432109876543210987654321"

# Mock API responses
MOCK_API_RESPONSE_200 = {
    "status": "ok",
    "data": [
        {
            "name": "Search API",
            "description": "Web search service",
            "endpoint": "/api/search",
            "price": "0.001 USDC",
        }
    ],
}

MOCK_API_RESPONSE_402 = {
    "error": "Payment required",
    "payment_details": {
        "amount": "0.001",
        "recipient": TEST_RECIPIENT_ADDRESS,
    },
}

MOCK_SERVICES_LIST = [
    {
        "id": "search-001",
        "name": "Web Search",
        "description": "Search the web",
        "endpoint": "/api/search",
        "price": "0.001 USDC",
    },
    {
        "id": "weather-001",
        "name": "Weather API",
        "description": "Get weather data",
        "endpoint": "/api/weather",
        "price": "0.001 USDC",
    },
    {
        "id": "image-001",
        "name": "Image Generation",
        "description": "Generate images with DALL-E 3",
        "endpoint": "/api/image",
        "price": "0.05 USDC",
    },
]

MOCK_MARKETPLACE_INFO = {
    "status": "healthy",
    "version": "1.0.0",
    "service_count": 8,
    "total_requests_served": 125000,
    "network": "base",
}


@pytest.fixture
def mock_session():
    """Create a mock requests.Session."""
    return MagicMock()


@pytest.fixture
def mock_web3():
    """Create a mock Web3 instance."""
    mock_w3 = MagicMock()
    mock_w3.eth.account.from_key.return_value = MagicMock(
        address=TEST_WALLET_ADDRESS, key=TEST_PRIVATE_KEY
    )
    mock_w3.eth.get_transaction_count.return_value = 42
    mock_w3.eth.gas_price = 1000000000
    mock_w3.eth.max_priority_fee = 1000000000
    mock_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
    mock_w3.eth.send_raw_transaction.return_value = (
        b"\x00" * 32
    )  # Mock transaction hash
    return mock_w3


@pytest.fixture
def mock_usdc_contract():
    """Create a mock USDC ERC20 contract."""
    mock_contract = MagicMock()
    mock_contract.functions.balanceOf.return_value.call.return_value = 10000000  # 10 USDC (6 decimals)
    mock_contract.functions.transfer.return_value.build_transaction.return_value = {
        "from": TEST_WALLET_ADDRESS,
        "to": TEST_RECIPIENT_ADDRESS,
        "value": 0,
        "data": "0x",
        "nonce": 42,
        "gas": 100000,
        "chainId": 8453,
    }
    return mock_contract


@pytest.fixture
def mock_response_200():
    """Mock successful HTTP 200 response."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = MOCK_API_RESPONSE_200
    response.text = json.dumps(MOCK_API_RESPONSE_200)
    return response


@pytest.fixture
def mock_response_402():
    """Mock HTTP 402 Payment Required response."""
    response = Mock()
    response.status_code = 402
    response.json.return_value = MOCK_API_RESPONSE_402
    response.text = json.dumps(MOCK_API_RESPONSE_402)
    return response


@pytest.fixture
def mock_response_404():
    """Mock HTTP 404 Not Found response."""
    response = Mock()
    response.status_code = 404
    response.json.return_value = {"error": "Not found"}
    response.text = '{"error": "Not found"}'
    return response


@pytest.fixture
def mock_response_500():
    """Mock HTTP 500 Server Error response."""
    response = Mock()
    response.status_code = 500
    response.json.return_value = {"error": "Internal server error"}
    response.text = '{"error": "Internal server error"}'
    return response


@pytest.fixture
def mock_response_services_list():
    """Mock response with services list."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = MOCK_SERVICES_LIST
    response.text = json.dumps(MOCK_SERVICES_LIST)
    return response


@pytest.fixture
def mock_response_marketplace_info():
    """Mock response with marketplace info."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = MOCK_MARKETPLACE_INFO
    response.text = json.dumps(MOCK_MARKETPLACE_INFO)
    return response


@pytest.fixture
def mock_response_402_no_recipient():
    """Mock HTTP 402 response without recipient address (error case)."""
    response = Mock()
    response.status_code = 402
    response.json.return_value = {
        "error": "Payment required",
        "payment_details": {
            "amount": "0.001",
        },
    }
    response.text = '{"error": "Payment required", "payment_details": {"amount": "0.001"}}'
    return response


@pytest.fixture
def x402_client_no_payment():
    """Create an X402Client without payment handler (for free endpoints)."""
    from x402_langchain.client import X402Client

    with patch("requests.Session"):
        return X402Client(
            private_key=None,
            base_url="https://test.example.com",
            chain="base",
            max_budget_usdc=1.0,
        )


@pytest.fixture
def x402_client_with_payment():
    """Create an X402Client with payment handler."""
    from x402_langchain.client import X402Client

    with patch("x402_langchain.client.X402PaymentHandler") as mock_payment_class:
        mock_payment = MagicMock()
        mock_payment.pay.return_value = "0x" + "b" * 64
        mock_payment.chain = "base"
        mock_payment_class.return_value = mock_payment

        client = X402Client(
            private_key=TEST_PRIVATE_KEY,
            base_url="https://test.example.com",
            chain="base",
            max_budget_usdc=1.0,
        )
        return client


@pytest.fixture
def payment_handler():
    """Create an X402PaymentHandler with mocked Web3."""
    from x402_langchain.payment import X402PaymentHandler

    with patch("x402_langchain.payment.Web3") as mock_web3_class:
        mock_w3 = MagicMock()
        mock_w3.eth.account.from_key.return_value = MagicMock(
            address=TEST_WALLET_ADDRESS, key=TEST_PRIVATE_KEY
        )
        mock_w3.eth.contract.return_value = MagicMock()
        mock_web3_class.return_value = mock_w3
        mock_web3_class.to_checksum_address = lambda x: x

        # Mock transaction hash returns (needs to be different for each call in tests)
        mock_w3.eth.send_raw_transaction.return_value = b"\x01" * 32

        handler = X402PaymentHandler(
            private_key=TEST_PRIVATE_KEY,
            chain="base",
            max_budget_usdc=10.0,
        )
        handler._w3 = mock_w3
        return handler
