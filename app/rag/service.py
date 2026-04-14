from typing import List
import asyncio

from app.rag.retriever import Retriever
from app.llm.service import LLMService


class RAGService:
    def __init__(self, llm: LLMService):
        self.retriever = Retriever()
        self.llm = llm

    # ================= NON-STREAM =================
    async def generate(self, query: str) -> str:
        chunks = await self.retriever.retrieve(query)
        print("RAG_SERVICE_CALLED")

        if not chunks:
            return "No relevant information found."

        context = "\n".join(chunks)

        prompt = f"""
Answer the user query using ONLY the provided context.

Context:
{context}

Query:
{query}

Answer:
"""

        response = await self.llm.generate(prompt, temperature=0, task="rag")

        return self._best_match(response, chunks)

    # ================= STREAM =================
    async def generate_stream(self, query: str):
        chunks = await self.retriever.retrieve(query)

        if not chunks:
            yield "No relevant information found."
            return

        context = "\n".join(chunks)

        prompt = f"""
Answer using context only.

Context:
{context}

Query:
{query}
"""

        async for token in self.llm.generate_stream(prompt, temperature=0):
            yield token
            await asyncio.sleep(0.02)

    # ================= ENFORCEMENT =================
    def _best_match(self, response: str, chunks: List[str]) -> str:
        if not response:
            return chunks[0]

        response_tokens = set(response.lower().split())

        best_chunk = chunks[0]
        best_score = -1

        for chunk in chunks:
            chunk_tokens = set(chunk.lower().split())
            score = len(response_tokens & chunk_tokens)

            if score > best_score:
                best_score = score
                best_chunk = chunk

        return best_chunk
