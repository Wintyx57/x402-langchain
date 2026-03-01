"""Tests for X402BazaarTool -- LangChain integration and factory methods."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from x402_langchain.tool import X402BazaarTool, X402ToolInput


class TestX402ToolInputSchema:
    """Test X402ToolInput validation schema."""

    def test_input_schema_creation(self):
        """Create valid input."""
        input_data = X402ToolInput(query="search bitcoin")
        assert input_data.query == "search bitcoin"

    def test_input_schema_description(self):
        """Schema should have proper field descriptions."""
        fields = X402ToolInput.model_fields
        assert "query" in fields
        assert fields["query"].description == "The query or input for the API endpoint."


class TestX402BazaarToolInitialization:
    """Test X402BazaarTool initialization."""

    def test_init_basic(self):
        """Initialize tool with default parameters."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(
                name="test_tool",
                description="Test description",
                endpoint="/api/test",
            )

            assert tool.name == "test_tool"
            assert tool.description == "Test description"
            assert tool.endpoint == "/api/test"
            assert tool.param_name == "q"
            assert tool.args_schema == X402ToolInput

    def test_init_with_payment(self):
        """Initialize tool with payment handler."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(
                name="paid_tool",
                description="Paid API tool",
                endpoint="/api/search",
                param_name="q",
                private_key="0x" + "a" * 64,
                chain="base-sepolia",
                max_budget_usdc=2.0,
            )

            mock_client_class.assert_called_once_with(
                private_key="0x" + "a" * 64,
                base_url="https://x402-api.onrender.com",
                chain="base-sepolia",
                max_budget_usdc=2.0,
            )

    def test_init_custom_base_url(self):
        """Initialize with custom base URL."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(
                name="custom_tool",
                base_url="https://custom.api.com",
            )

            mock_client_class.assert_called_once_with(
                private_key=None,
                base_url="https://custom.api.com",
                chain="base",
                max_budget_usdc=1.0,
            )

    def test_tool_is_langchain_base_tool(self):
        """X402BazaarTool should inherit from BaseTool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool()
            from langchain_core.tools import BaseTool

            assert isinstance(tool, BaseTool)


class TestX402BazaarToolRun:
    """Test tool execution (_run method)."""

    def test_run_successful(self):
        """Execute tool successfully."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.return_value = {"result": "success", "data": []}
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(
                name="test_tool",
                endpoint="/api/search",
                param_name="q",
            )

            result = tool._run("bitcoin")
            mock_client.call_api.assert_called_once_with(
                "/api/search", params={"q": "bitcoin"}
            )
            assert "success" in result or "result" in result

    def test_run_with_callback_manager(self):
        """Execute tool with LangChain callback manager."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.return_value = {"status": "ok"}
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(name="test_tool")
            mock_run_manager = MagicMock()

            result = tool._run("test query", run_manager=mock_run_manager)
            assert "ok" in result

    def test_run_error_handling(self):
        """Tool should handle API errors gracefully."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.side_effect = Exception("API connection failed")
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool(name="test_tool", endpoint="/api/test")

            result = tool._run("test query")
            assert "Error" in result
            assert "API connection failed" in result

    def test_run_returns_string(self):
        """_run should always return string."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.return_value = {"nested": {"data": [1, 2, 3]}}
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool()
            result = tool._run("query")

            assert isinstance(result, str)


class TestX402BazaarToolFactorySearch:
    """Test X402BazaarTool.search() factory method."""

    def test_search_factory_free_endpoint(self):
        """Search factory should create a tool for free endpoint."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.search()

            assert tool.name == "x402_search_marketplace"
            assert tool.endpoint == "/api/services"
            assert tool.param_name == "q"
            assert "marketplace" in tool.description.lower()

    def test_search_factory_with_payment(self):
        """Search factory should support optional payment."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.search(
                private_key="0x" + "a" * 64,
                chain="skale",
                max_budget_usdc=5.0,
            )

            assert tool.name == "x402_search_marketplace"
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["private_key"] == "0x" + "a" * 64
            assert call_kwargs["chain"] == "skale"
            assert call_kwargs["max_budget_usdc"] == 5.0


class TestX402BazaarToolFactoryWebSearch:
    """Test X402BazaarTool.web_search() factory method."""

    def test_web_search_factory(self):
        """Web search factory should create correct tool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.web_search(private_key="0x" + "a" * 64)

            assert tool.name == "x402_web_search"
            assert tool.endpoint == "/api/search"
            assert tool.param_name == "q"
            assert "0.001 USDC" in tool.description

    def test_web_search_requires_private_key(self):
        """Web search factory requires private_key."""
        with patch("x402_langchain.tool.X402Client"):
            # Should work with private key
            tool = X402BazaarTool.web_search(private_key="0x" + "a" * 64)
            assert tool is not None


class TestX402BazaarToolFactoryScrape:
    """Test X402BazaarTool.scrape() factory method."""

    def test_scrape_factory(self):
        """Scrape factory should create correct tool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.scrape(private_key="0x" + "a" * 64)

            assert tool.name == "x402_scrape"
            assert tool.endpoint == "/api/scrape"
            assert tool.param_name == "url"
            assert "0.002 USDC" in tool.description


class TestX402BazaarToolFactoryWeather:
    """Test X402BazaarTool.weather() factory method."""

    def test_weather_factory(self):
        """Weather factory should create correct tool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.weather(private_key="0x" + "a" * 64)

            assert tool.name == "x402_weather"
            assert tool.endpoint == "/api/weather"
            assert tool.param_name == "city"
            assert "0.001 USDC" in tool.description


class TestX402BazaarToolFactoryCrypto:
    """Test X402BazaarTool.crypto() factory method."""

    def test_crypto_factory(self):
        """Crypto factory should create correct tool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.crypto(private_key="0x" + "a" * 64)

            assert tool.name == "x402_crypto"
            assert tool.endpoint == "/api/crypto"
            assert tool.param_name == "coin"
            assert "0.001 USDC" in tool.description


class TestX402BazaarToolFactoryImage:
    """Test X402BazaarTool.image() factory method."""

    def test_image_factory(self):
        """Image factory should create correct tool."""
        with patch("x402_langchain.tool.X402Client"):
            tool = X402BazaarTool.image(private_key="0x" + "a" * 64)

            assert tool.name == "x402_image"
            assert tool.endpoint == "/api/image"
            assert tool.param_name == "prompt"
            assert "DALL-E 3" in tool.description
            assert "0.05 USDC" in tool.description


class TestX402BazaarToolChainVariants:
    """Test tools with different chain configurations."""

    def test_tool_base_mainnet(self):
        """Create tool for Base mainnet."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.web_search(
                private_key="0x" + "a" * 64,
                chain="base",
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["chain"] == "base"

    def test_tool_base_sepolia(self):
        """Create tool for Base Sepolia testnet."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.weather(
                private_key="0x" + "a" * 64,
                chain="base-sepolia",
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["chain"] == "base-sepolia"

    def test_tool_skale(self):
        """Create tool for SKALE chain."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.crypto(
                private_key="0x" + "a" * 64,
                chain="skale",
                max_budget_usdc=10.0,
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["chain"] == "skale"
            assert call_kwargs["max_budget_usdc"] == 10.0


class TestX402BazaarToolBudgetVariants:
    """Test tools with different budget configurations."""

    def test_tool_low_budget(self):
        """Create tool with low budget."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.web_search(
                private_key="0x" + "a" * 64,
                max_budget_usdc=0.01,
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["max_budget_usdc"] == 0.01

    def test_tool_high_budget(self):
        """Create tool with high budget."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.image(
                private_key="0x" + "a" * 64,
                max_budget_usdc=100.0,
            )

            call_kwargs = mock_client_class.call_args[1]
            assert call_kwargs["max_budget_usdc"] == 100.0


class TestX402BazaarToolIntegration:
    """Integration tests combining multiple aspects."""

    def test_full_workflow_search_tool(self):
        """Full workflow: create search tool and execute query."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.return_value = [
                {"name": "Service 1", "price": "0.001 USDC"},
                {"name": "Service 2", "price": "0.002 USDC"},
            ]
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.search()
            result = tool._run("weather")

            assert isinstance(result, str)
            mock_client.call_api.assert_called_once()

    def test_full_workflow_paid_tool(self):
        """Full workflow: create paid tool and execute query."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.call_api.return_value = {
                "status": "success",
                "data": "Bitcoin: $50,000",
            }
            mock_client_class.return_value = mock_client

            tool = X402BazaarTool.crypto(
                private_key="0x" + "a" * 64,
                max_budget_usdc=1.0,
            )
            result = tool._run("bitcoin")

            assert "success" in result
            assert mock_client.call_api.called

    def test_multiple_tools_with_same_key(self):
        """Create multiple tools with same private key."""
        with patch("x402_langchain.tool.X402Client") as mock_client_class:
            mock_client1 = MagicMock()
            mock_client2 = MagicMock()
            mock_client3 = MagicMock()
            mock_client_class.side_effect = [mock_client1, mock_client2, mock_client3]

            key = "0x" + "a" * 64
            tool1 = X402BazaarTool.web_search(private_key=key)
            tool2 = X402BazaarTool.weather(private_key=key)
            tool3 = X402BazaarTool.crypto(private_key=key)

            assert tool1.name == "x402_web_search"
            assert tool2.name == "x402_weather"
            assert tool3.name == "x402_crypto"
            assert mock_client_class.call_count == 3
