"""x402 Bazaar API client -- handles requests and automatic x402 payment flow."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

import requests

from x402_langchain.payment import X402PaymentHandler

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://x402-api.onrender.com"
DEFAULT_TIMEOUT = 30


class X402APIError(Exception):
    """Raised when the x402 Bazaar API returns an unexpected error."""


class X402Client:
    """API client for x402 Bazaar with automatic x402 payment flow.

    When an endpoint returns HTTP 402, the client automatically:
    1. Extracts payment details from the response body
    2. Sends USDC on-chain via the payment handler
    3. Retries the request with the X-Payment-TxHash header

    Args:
        private_key: Hex-encoded private key for USDC payments.
        base_url: Base URL of the x402 Bazaar API.
        chain: Chain identifier -- "base", "base-sepolia", or "skale".
        max_budget_usdc: Maximum cumulative spend in USDC.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "x402-langchain/0.1.0"

        self._payment: Optional[X402PaymentHandler] = None
        if private_key:
            self._payment = X402PaymentHandler(
                private_key=private_key,
                chain=chain,
                max_budget_usdc=max_budget_usdc,
            )

    @property
    def payment_handler(self) -> Optional[X402PaymentHandler]:
        """The underlying payment handler, if configured."""
        return self._payment

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make an HTTP request, handling the x402 payment flow automatically.

        Args:
            method: HTTP method (GET, POST).
            path: API path (e.g., "/api/search").
            params: Query parameters.
            json_body: JSON body for POST requests.

        Returns:
            Parsed JSON response.

        Raises:
            X402APIError: On non-2xx responses (after payment retry).
        """
        url = f"{self._base_url}{path}"

        resp = self._session.request(
            method,
            url,
            params=params,
            json=json_body,
            timeout=self._timeout,
        )

        # x402 payment flow
        if resp.status_code == 402:
            if not self._payment:
                raise X402APIError(
                    "Endpoint requires payment (HTTP 402) but no private_key was provided. "
                    "Initialize X402Client with a private_key to enable automatic payments."
                )

            body = resp.json()
            payment_details = body.get("payment_details", {})
            amount_str = payment_details.get("amount", "0")
            recipient = payment_details.get("recipient")

            if not recipient:
                raise X402APIError(
                    f"402 response missing recipient address: {body}"
                )

            amount = float(amount_str)
            logger.info(
                "Received 402 for %s -- paying %.4f USDC to %s",
                path,
                amount,
                recipient[:10] + "...",
            )

            tx_hash = self._payment.pay(amount, recipient)

            # Retry with payment proof
            headers = {
                "X-Payment-TxHash": tx_hash,
                "X-Payment-Chain": self._payment.chain,
            }
            resp = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self._timeout,
            )

        if resp.status_code >= 400:
            raise X402APIError(
                f"API error {resp.status_code}: {resp.text[:500]}"
            )

        return resp.json()

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for services on the marketplace.

        Args:
            query: Search query string.

        Returns:
            List of matching service objects.
        """
        data = self._request("GET", "/api/services", params={"q": query})
        if isinstance(data, list):
            return data
        return data.get("services", data.get("data", []))

    def list_services(self) -> List[Dict[str, Any]]:
        """List all services on the marketplace.

        Returns:
            List of all service objects.
        """
        data = self._request("GET", "/api/services")
        if isinstance(data, list):
            return data
        return data.get("services", data.get("data", []))

    def call_api(self, path: str, params: Optional[Dict[str, str]] = None) -> Any:
        """Call any x402 Bazaar API endpoint.

        Handles the 402 payment flow automatically.

        Args:
            path: API path (e.g., "/api/search", "/api/weather").
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        return self._request("GET", path, params=params)

    def get_info(self) -> Dict[str, Any]:
        """Get marketplace information (health + stats).

        Returns:
            Dict with marketplace status, service count, and network info.
        """
        return self._request("GET", "/")

    def web_search(self, query: str) -> Any:
        """Run a web search via the x402 search wrapper.

        Args:
            query: Search query.

        Returns:
            Search results.
        """
        return self._request("GET", "/api/search", params={"q": query})

    def scrape(self, url: str) -> Any:
        """Scrape a webpage via the x402 scraper wrapper.

        Args:
            url: URL to scrape.

        Returns:
            Scraped content (markdown).
        """
        return self._request("GET", "/api/scrape", params={"url": url})

    def weather(self, city: str) -> Any:
        """Get weather data via the x402 weather wrapper.

        Args:
            city: City name.

        Returns:
            Weather data.
        """
        return self._request("GET", "/api/weather", params={"city": city})

    def crypto(self, coin: str = "bitcoin") -> Any:
        """Get cryptocurrency prices via the x402 crypto wrapper.

        Args:
            coin: Coin identifier (e.g., "bitcoin", "ethereum").

        Returns:
            Price data.
        """
        return self._request("GET", "/api/crypto", params={"coin": coin})

    def generate_image(self, prompt: str) -> Any:
        """Generate an image via DALL-E 3 through the x402 image wrapper.

        Args:
            prompt: Image description prompt.

        Returns:
            Generated image URL and metadata.
        """
        return self._request("GET", "/api/image", params={"prompt": prompt})
