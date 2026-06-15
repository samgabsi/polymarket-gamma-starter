import asyncio

from app.gamma_client import GammaClient


async def main() -> None:
    client = GammaClient()
    events = await client.list_events(limit=3)
    markets = await client.list_markets(limit=3)
    print(f"Fetched {len(events)} events and {len(markets)} markets from Gamma.")
    if events:
        print("Top event:", events[0]["title"])
    if markets:
        print("Top market:", markets[0]["question"])


if __name__ == "__main__":
    asyncio.run(main())
