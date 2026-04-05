import asyncio
from app.rag.retriever import Retriever


queries = [
    "i didnt receive my package",
    "item came broken",
    "how long does shipping take",
    "can i cancel after ordering",
]


async def main():
    retriever = Retriever()

    for q in queries:
        chunks = await retriever.retrieve(q)

        print("\nQUERY:", q)
        for c in chunks:
            print("-", c[:120])


asyncio.run(main())
