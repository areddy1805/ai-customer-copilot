import asyncio
import json

from app.rag.retriever import Retriever


async def run():
    retriever = Retriever()

    with open("app/eval/test_cases.json") as f:
        test_cases = json.load(f)

    correct = 0

    for case in test_cases:
        query = case["query"]
        expected = case["expected"]

        chunks = await retriever.retrieve(query)

        hit = any(expected in c.lower() for c in chunks)

        print("\nQUERY:", query)
        print("EXPECTED:", expected)
        print("CHUNKS:")
        for c in chunks:
            print("-", c[:120])

        print("RESULT:", "PASS" if hit else "FAIL")

        if hit:
            correct += 1

    print("\nFINAL SCORE:", correct, "/", len(test_cases))


asyncio.run(run())
