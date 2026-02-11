"""LangChain tool wrapper for x402 Bazaar API endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from x402_langchain.client import X402Client

logger = logging.getLogger(__name__)


class X402ToolInput(BaseModel):
    """Input schema for X402BazaarTool."""

    query: str = Field(description="The query or input for the API endpoint.")


class X402BazaarTool(BaseTool):
    """LangChain tool that calls x402 Bazaar API endpoints with automatic USDC payments.

    When a paid endpoint returns HTTP 402, the tool automatically handles
    the payment flow: pay USDC on-chain, then retry with the transaction hash.

    Args:
        name: Tool name visible to the LLM agent.
        description: Description of what the tool does (used by the agent to decide when to use it).
        endpoint: API path on x402 Bazaar (e.g., "/api/search").
        param_name: Query parameter name for the input (e.g., "q", "city", "url").
        private_key: Hex-encoded private key for USDC payments (optional for free endpoints).
        chain: Chain identifier -- "base", "base-sepolia", or "skale".
        max_budget_usdc: Maximum cumulative USDC spend.
        base_url: Base URL of the x402 Bazaar API.
    """

    name: str = "x402_bazaar"
    description: str = "Query the x402 Bazaar API marketplace"
    endpoint: str = "/api/services"
    param_name: str = "q"
    args_schema: Type[BaseModel] = X402ToolInput

    # Private fields (not exposed to Pydantic model schema)
    _client: X402Client

    def __init__(
        self,
        name: str = "x402_bazaar",
        description: str = "Query the x402 Bazaar API marketplace",
        endpoint: str = "/api/services",
        param_name: str = "q",
        private_key: Optional[str] = None,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
        base_url: str = "https://x402-api.onrender.com",
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            endpoint=endpoint,
            param_name=param_name,
        )
        self._client = X402Client(
            private_key=private_key,
            base_url=base_url,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the tool: call the x402 Bazaar endpoint.

        Args:
            query: The user query or input value.
            run_manager: LangChain callback manager (optional).

        Returns:
            String representation of the API response.
        """
        try:
            result = self._client.call_api(
                self.endpoint, params={self.param_name: query}
            )
            return str(result)
        except Exception as exc:
            return f"Error calling x402 Bazaar ({self.endpoint}): {exc}"

    # ---- Pre-configured factory methods ----

    @classmethod
    def search(
        cls,
        private_key: Optional[str] = None,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Search the x402 Bazaar marketplace for services.

        This is a FREE endpoint -- no private_key required.
        """
        return cls(
            name="x402_search_marketplace",
            description=(
                "Search the x402 Bazaar marketplace for API services. "
                "Input is a search query. Returns matching services with "
                "name, description, price, and endpoint URL."
            ),
            endpoint="/api/services",
            param_name="q",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    @classmethod
    def web_search(
        cls,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Web search tool (DuckDuckGo) -- costs 0.001 USDC per query."""
        return cls(
            name="x402_web_search",
            description=(
                "Search the web using x402 Bazaar's search API (DuckDuckGo). "
                "Costs 0.001 USDC per query, paid automatically in USDC. "
                "Input is the search query. Returns web search results."
            ),
            endpoint="/api/search",
            param_name="q",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    @classmethod
    def scrape(
        cls,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Web scraper tool -- costs 0.002 USDC per page."""
        return cls(
            name="x402_scrape",
            description=(
                "Scrape a webpage and extract its content as markdown "
                "using x402 Bazaar's scraper API. Costs 0.002 USDC per page. "
                "Input is the full URL to scrape (e.g., https://example.com)."
            ),
            endpoint="/api/scrape",
            param_name="url",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    @classmethod
    def weather(
        cls,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Weather data tool -- costs 0.001 USDC per query."""
        return cls(
            name="x402_weather",
            description=(
                "Get current weather data for a city using x402 Bazaar's "
                "weather API. Costs 0.001 USDC per query. "
                "Input is the city name (e.g., 'Paris', 'New York')."
            ),
            endpoint="/api/weather",
            param_name="city",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    @classmethod
    def crypto(
        cls,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Cryptocurrency price tool -- costs 0.001 USDC per query."""
        return cls(
            name="x402_crypto",
            description=(
                "Get current cryptocurrency prices using x402 Bazaar's "
                "crypto API. Costs 0.001 USDC per query. "
                "Input is the coin name (e.g., 'bitcoin', 'ethereum', 'solana')."
            ),
            endpoint="/api/crypto",
            param_name="coin",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )

    @classmethod
    def image(
        cls,
        private_key: str,
        chain: str = "base",
        max_budget_usdc: float = 1.0,
    ) -> X402BazaarTool:
        """Image generation tool (DALL-E 3) -- costs 0.05 USDC per image."""
        return cls(
            name="x402_image",
            description=(
                "Generate an image using DALL-E 3 via x402 Bazaar's image API. "
                "Costs 0.05 USDC per image. "
                "Input is a text description of the image to generate."
            ),
            endpoint="/api/image",
            param_name="prompt",
            private_key=private_key,
            chain=chain,
            max_budget_usdc=max_budget_usdc,
        )
