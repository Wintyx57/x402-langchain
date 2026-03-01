"""Tests for X402Client -- HTTP requests and 402 payment flow."""

from unittest.mock import MagicMock, patch

import pytest

from x402_langchain.client import X402APIError, X402Client


class TestX402ClientInitialization:
    """Test X402Client initialization."""

    def test_init_without_payment(self):
        """Initialize client without private key (free endpoints only)."""
        with patch("requests.Session"):
            client = X402Client(
                private_key=None,
                base_url="https://api.test.com",
                chain="base",
                max_budget_usdc=1.0,
            )
            assert client.payment_handler is None
            assert client._base_url == "https://api.test.com"

    def test_init_with_payment(self):
        """Initialize client with private key (enables payments)."""
        with patch("x402_langchain.client.X402PaymentHandler") as mock_handler:
            mock_handler.return_value = MagicMock()
            client = X402Client(
                private_key="0x" + "a" * 64,
                base_url="https://api.test.com",
                chain="base-sepolia",
                max_budget_usdc=5.0,
            )
            assert client.payment_handler is not None
            mock_handler.assert_called_once_with(
                private_key="0x" + "a" * 64,
                chain="base-sepolia",
                max_budget_usdc=5.0,
            )

    def test_init_strips_trailing_slash(self):
        """Base URL should have trailing slash removed."""
        with patch("requests.Session"):
            client = X402Client(base_url="https://api.test.com/")
            assert client._base_url == "https://api.test.com"

    def test_init_user_agent(self):
        """Client should set appropriate User-Agent."""
        with patch("requests.Session") as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            X402Client()
            mock_session_instance.headers.__setitem__.assert_called()


class TestX402ClientRequests:
    """Test HTTP request handling."""

    def test_successful_get_request(self, x402_client_no_payment, mock_response_200):
        """Successfully execute a GET request."""
        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_no_payment._request("GET", "/api/test")
            assert result == mock_response_200.json.return_value
            x402_client_no_payment._session.request.assert_called_once()

    def test_successful_get_with_params(
        self, x402_client_no_payment, mock_response_200
    ):
        """GET request with query parameters."""
        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_no_payment._request(
                "GET", "/api/search", params={"q": "bitcoin"}
            )
            assert result == mock_response_200.json.return_value
            call_args = x402_client_no_payment._session.request.call_args
            assert call_args[1]["params"] == {"q": "bitcoin"}

    def test_error_404_not_found(self, x402_client_no_payment, mock_response_404):
        """HTTP 404 should raise X402APIError."""
        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response_404
        ):
            with pytest.raises(X402APIError, match="API error 404"):
                x402_client_no_payment._request("GET", "/api/notfound")

    def test_error_500_server_error(
        self, x402_client_no_payment, mock_response_500
    ):
        """HTTP 500 should raise X402APIError."""
        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response_500
        ):
            with pytest.raises(X402APIError, match="API error 500"):
                x402_client_no_payment._request("GET", "/api/test")


class TestX402ClientPaymentFlow:
    """Test HTTP 402 payment flow."""

    def test_402_payment_required_with_handler(self, x402_client_with_payment):
        """HTTP 402 triggers payment flow with valid handler."""
        from tests.conftest import (
            MOCK_API_RESPONSE_402,
            TEST_RECIPIENT_ADDRESS,
            mock_response_200,
        )

        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = MOCK_API_RESPONSE_402

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"result": "success"}

        with patch.object(
            x402_client_with_payment._session,
            "request",
            side_effect=[mock_402, mock_200],
        ):
            result = x402_client_with_payment._request("GET", "/api/paid")

            # Verify payment was initiated
            x402_client_with_payment.payment_handler.pay.assert_called_once_with(
                0.001, TEST_RECIPIENT_ADDRESS
            )

            # Verify retry with payment headers
            assert x402_client_with_payment._session.request.call_count == 2
            second_call = x402_client_with_payment._session.request.call_args_list[1]
            assert "headers" in second_call[1]
            assert "X-Payment-TxHash" in second_call[1]["headers"]

    def test_402_without_payment_handler(self, x402_client_no_payment):
        """HTTP 402 without payment handler raises error."""
        from tests.conftest import MOCK_API_RESPONSE_402

        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = MOCK_API_RESPONSE_402

        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_402
        ):
            with pytest.raises(
                X402APIError,
                match="Endpoint requires payment.*no private_key was provided",
            ):
                x402_client_no_payment._request("GET", "/api/paid")

    def test_402_missing_recipient(self, x402_client_with_payment):
        """HTTP 402 without recipient address raises error."""
        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = {
            "error": "Payment required",
            "payment_details": {"amount": "0.001"},
        }

        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_402
        ):
            with pytest.raises(X402APIError, match="402 response missing recipient"):
                x402_client_with_payment._request("GET", "/api/paid")

    def test_402_invalid_amount(self, x402_client_with_payment):
        """HTTP 402 with invalid amount raises error during float conversion."""
        from tests.conftest import TEST_RECIPIENT_ADDRESS

        mock_402 = MagicMock()
        mock_402.status_code = 402
        mock_402.json.return_value = {
            "error": "Payment required",
            "payment_details": {
                "amount": "invalid",
                "recipient": TEST_RECIPIENT_ADDRESS,
            },
        }

        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_402
        ):
            with pytest.raises(ValueError):
                x402_client_with_payment._request("GET", "/api/paid")


class TestX402ClientAPIMethods:
    """Test high-level API methods."""

    def test_search(self, x402_client_no_payment, mock_response_services_list):
        """Search for services."""
        with patch.object(
            x402_client_no_payment._session,
            "request",
            return_value=mock_response_services_list,
        ):
            results = x402_client_no_payment.search("weather")
            assert len(results) == 3
            assert results[0]["name"] == "Web Search"

    def test_list_services(self, x402_client_no_payment, mock_response_services_list):
        """List all services."""
        with patch.object(
            x402_client_no_payment._session,
            "request",
            return_value=mock_response_services_list,
        ):
            services = x402_client_no_payment.list_services()
            assert len(services) == 3
            x402_client_no_payment._session.request.assert_called_with(
                "GET",
                "https://test.example.com/api/services",
                params=None,
                json=None,
                timeout=30,
            )

    def test_call_api(self, x402_client_no_payment, mock_response_200):
        """Call arbitrary API endpoint."""
        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_no_payment.call_api("/api/custom", params={"key": "value"})
            assert result == mock_response_200.json.return_value

    def test_get_info(self, x402_client_no_payment, mock_response_marketplace_info):
        """Get marketplace information."""
        with patch.object(
            x402_client_no_payment._session,
            "request",
            return_value=mock_response_marketplace_info,
        ):
            info = x402_client_no_payment.get_info()
            assert info["status"] == "healthy"
            assert info["service_count"] == 8

    def test_web_search(self, x402_client_with_payment, mock_response_200):
        """Execute web search."""
        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_with_payment.web_search("python tutorials")
            assert result == mock_response_200.json.return_value

    def test_scrape(self, x402_client_with_payment, mock_response_200):
        """Scrape a URL."""
        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_with_payment.scrape("https://example.com")
            call_args = x402_client_with_payment._session.request.call_args
            assert call_args[1]["params"]["url"] == "https://example.com"

    def test_weather(self, x402_client_with_payment, mock_response_200):
        """Get weather data."""
        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_with_payment.weather("Paris")
            call_args = x402_client_with_payment._session.request.call_args
            assert call_args[1]["params"]["city"] == "Paris"

    def test_crypto(self, x402_client_with_payment, mock_response_200):
        """Get cryptocurrency prices."""
        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_with_payment.crypto("ethereum")
            call_args = x402_client_with_payment._session.request.call_args
            assert call_args[1]["params"]["coin"] == "ethereum"

    def test_generate_image(self, x402_client_with_payment, mock_response_200):
        """Generate image via DALL-E."""
        with patch.object(
            x402_client_with_payment._session, "request", return_value=mock_response_200
        ):
            result = x402_client_with_payment.generate_image("a cat in space")
            call_args = x402_client_with_payment._session.request.call_args
            assert call_args[1]["params"]["prompt"] == "a cat in space"


class TestX402ClientResponseParsing:
    """Test response parsing edge cases."""

    def test_list_response_as_array(self, x402_client_no_payment):
        """Response as direct array instead of dict with 'services' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "Service 1"}]

        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response
        ):
            result = x402_client_no_payment.list_services()
            assert isinstance(result, list)
            assert len(result) == 1

    def test_list_response_with_services_key(self, x402_client_no_payment):
        """Response with 'services' key."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "services": [{"id": 1, "name": "Service 1"}]
        }

        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response
        ):
            result = x402_client_no_payment.list_services()
            assert isinstance(result, list)
            assert len(result) == 1

    def test_list_response_with_data_key(self, x402_client_no_payment):
        """Response with 'data' key fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1, "name": "Service 1"}]}

        with patch.object(
            x402_client_no_payment._session, "request", return_value=mock_response
        ):
            result = x402_client_no_payment.list_services()
            assert isinstance(result, list)
            assert len(result) == 1
