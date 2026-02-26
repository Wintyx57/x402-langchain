# x402-langchain

LangChain tools for [x402 Bazaar](https://x402bazaar.org) -- the AI agent API marketplace with native USDC payments.

Build autonomous AI agents that can search the web, scrape pages, check weather, get crypto prices, and more -- all paid automatically with USDC on Base or SKALE.

## Installation

```bash
pip install x402-langchain
```

## Quick Start

### Free endpoint (no wallet needed)

```python
from x402_langchain import X402Client

client = X402Client()
services = client.search("weather")
print(f"Found {len(services)} services")
```

### Paid endpoint (automatic USDC payment)

```python
from x402_langchain import X402Client

client = X402Client(
    private_key="0xYOUR_PRIVATE_KEY",
    chain="base",           # "base", "base-sepolia", or "skale"
    max_budget_usdc=1.0,    # Safety cap
)

# Automatically pays 0.001 USDC and returns results
results = client.web_search("latest AI news")
print(results)
```

### LangChain Agent

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from x402_langchain import X402BazaarTool

tools = [
    X402BazaarTool.search(),   # Free
    X402BazaarTool.web_search(private_key="0x..."),
    X402BazaarTool.weather(private_key="0x..."),
    X402BazaarTool.crypto(private_key="0x..."),
]

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with x402 Bazaar tools."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": "What's the weather in Tokyo?"})
```

## Available Tools

| Tool | Endpoint | Cost | Description |
|------|----------|------|-------------|
| `X402BazaarTool.search()` | `/api/services` | Free | Search the marketplace |
| `X402BazaarTool.web_search()` | `/api/search` | 0.001 USDC | Web search (DuckDuckGo) |
| `X402BazaarTool.scrape()` | `/api/scrape` | 0.002 USDC | Scrape any webpage to markdown |
| `X402BazaarTool.weather()` | `/api/weather` | 0.001 USDC | Current weather data |
| `X402BazaarTool.crypto()` | `/api/crypto` | 0.001 USDC | Cryptocurrency prices |
| `X402BazaarTool.image()` | `/api/image` | 0.05 USDC | Image generation (DALL-E 3) |

## Configuration

### Supported Chains

| Chain | ID | Gas Cost |
|-------|----|----------|
| Base Mainnet | `base` | ~$0.001 |
| Base Sepolia (testnet) | `base-sepolia` | Free |
| SKALE Europa | `skale` | Free (sFUEL) |

### Budget Control

The `max_budget_usdc` parameter prevents runaway spending:

```python
client = X402Client(
    private_key="0x...",
    max_budget_usdc=0.50,  # Will refuse payments after spending 0.50 USDC
)
```

### Using the Client Directly

```python
from x402_langchain import X402Client

client = X402Client(private_key="0x...", chain="base")

# Any x402 endpoint
result = client.call_api("/api/weather", params={"city": "London"})

# Check spending
print(f"Spent: {client.payment_handler.total_spent} USDC")
print(f"Remaining: {client.payment_handler.remaining_budget} USDC")
print(f"USDC Balance: {client.payment_handler.get_balance()} USDC")
```

## How x402 Payment Works

1. Your agent calls a paid API endpoint
2. The server responds with HTTP 402 and payment details
3. x402-langchain automatically transfers USDC on-chain
4. The request is retried with the transaction hash
5. The server verifies the payment and returns data

All of this happens transparently -- your agent just calls the tool.

## API Reference

### X402Client

```python
X402Client(
    private_key: str = None,    # Wallet private key (optional for free endpoints)
    base_url: str = "https://x402-api.onrender.com",
    chain: str = "base",
    max_budget_usdc: float = 1.0,
    timeout: int = 30,
)
```

Methods: `search()`, `list_services()`, `call_api()`, `get_info()`, `web_search()`, `scrape()`, `weather()`, `crypto()`, `generate_image()`

### X402BazaarTool

```python
X402BazaarTool(
    name: str,
    description: str,
    endpoint: str,
    param_name: str = "q",
    private_key: str = None,
    chain: str = "base",
    max_budget_usdc: float = 1.0,
)
```

Factory methods: `search()`, `web_search()`, `scrape()`, `weather()`, `crypto()`, `image()`

### X402PaymentHandler

```python
X402PaymentHandler(
    private_key: str,
    chain: str = "base",
    max_budget_usdc: float = 1.0,
)
```

Properties: `address`, `chain`, `total_spent`, `remaining_budget`
Methods: `pay()`, `get_balance()`

## Ecosystem

| Repository | Description |
|---|---|
| **[x402-backend](https://github.com/Wintyx57/x402-backend)** | API server, 69 native endpoints, payment middleware, MCP server |
| **[x402-frontend](https://github.com/Wintyx57/x402-frontend)** | React + TypeScript UI, wallet connect |
| **[x402-bazaar-cli](https://github.com/Wintyx57/x402-bazaar-cli)** | `npx x402-bazaar` -- CLI with 7 commands |
| **[x402-sdk](https://github.com/Wintyx57/x402-sdk)** | TypeScript SDK for AI agents |
| **[x402-langchain](https://github.com/Wintyx57/x402-langchain)** | Python LangChain tools (this repo) |
| **[x402-fast-monetization-template](https://github.com/Wintyx57/x402-fast-monetization-template)** | FastAPI template to monetize any Python function |

**Live:** [x402bazaar.org](https://x402bazaar.org) | **API:** [x402-api.onrender.com](https://x402-api.onrender.com)
