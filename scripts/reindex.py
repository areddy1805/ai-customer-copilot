import asyncio
from app.rag.indexer import Indexer


async def main():
    indexer = Indexer()
    await indexer.run()


asyncio.run(main())