"""Full LangChain agent demo with multiple x402 Bazaar tools.

Requirements:
    pip install x402-langchain langchain-openai

Usage:
    export OPENAI_API_KEY="sk-..."
    export X402_PRIVATE_KEY="0x..."   # Your wallet private key (with USDC on Base)
    python agent_demo.py
"""

import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from x402_langchain import X402BazaarTool

# ---- Configuration ----

PRIVATE_KEY = os.environ.get("X402_PRIVATE_KEY", "")
CHAIN = os.environ.get("X402_CHAIN", "base")
MAX_BUDGET = float(os.environ.get("X402_MAX_BUDGET", "0.50"))

if not PRIVATE_KEY:
    print("Set X402_PRIVATE_KEY environment variable to your wallet private key.")
    print("The wallet must hold USDC on Base (or the configured chain).")
    raise SystemExit(1)

# ---- Create x402 tools ----

tools = [
    X402BazaarTool.search(),  # Free -- search the marketplace
    X402BazaarTool.web_search(private_key=PRIVATE_KEY, chain=CHAIN, max_budget_usdc=MAX_BUDGET),
    X402BazaarTool.weather(private_key=PRIVATE_KEY, chain=CHAIN, max_budget_usdc=MAX_BUDGET),
    X402BazaarTool.crypto(private_key=PRIVATE_KEY, chain=CHAIN, max_budget_usdc=MAX_BUDGET),
    X402BazaarTool.scrape(private_key=PRIVATE_KEY, chain=CHAIN, max_budget_usdc=MAX_BUDGET),
]

print(f"Loaded {len(tools)} x402 Bazaar tools:")
for t in tools:
    print(f"  - {t.name}: {t.description[:80]}...")

# ---- Build the agent ----

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a research assistant with access to x402 Bazaar tools. "
            "These tools let you search the web, check weather, get crypto prices, "
            "and scrape webpages. Each paid tool costs a small amount of USDC "
            "that is automatically handled. Use the tools to answer the user's question.",
        ),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# ---- Run a research task ----

question = "What's the current weather in Paris and the price of Bitcoin?"
print(f"\n{'='*60}")
print(f"Question: {question}")
print(f"{'='*60}\n")

result = executor.invoke({"input": question})
print(f"\n{'='*60}")
print(f"Answer: {result['output']}")
print(f"{'='*60}")
