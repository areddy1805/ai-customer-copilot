import asyncio
from app.frameworks.autogen.runner import AutoGenAdapter


async def main():
    adapter = AutoGenAdapter()
    result = await adapter.run("Track ORD1")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
