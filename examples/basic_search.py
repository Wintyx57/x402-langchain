"""Basic example: search the x402 Bazaar marketplace (free endpoint)."""

from x402_langchain import X402Client

# No private key needed for marketplace search (free endpoint)
client = X402Client()

# Search for services
print("=== Searching for 'weather' services ===")
results = client.search("weather")
for svc in results[:5]:
    print(f"  - {svc.get('name', 'N/A')} | {svc.get('price_usdc', '?')} USDC | {svc.get('url', '')}")

# List all services
print(f"\n=== All services ({len(client.list_services())} total) ===")
for svc in client.list_services()[:10]:
    print(f"  - {svc.get('name', 'N/A')}")

# Get marketplace info
print("\n=== Marketplace info ===")
info = client.get_info()
print(f"  Status: {info.get('status', 'unknown')}")
print(f"  Network: {info.get('network', 'unknown')}")
