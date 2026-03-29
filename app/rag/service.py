from typing import List
import asyncio

from app.rag.retriever import Retriever
from app.llm.service import LLMService
from app.llm.models import TaskType


class RAGService:
    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()

    # ================= NON-STREAM =================
    async def generate(self, query: str) -> str:
        chunks = self.retriever.retrieve(query)

        if not chunks:
            return "No relevant information found."

        context = "\n".join(chunks)

        response = await self.llm.generate(TaskType.RAG, query, context=context)

        return self._enforce_strict_rag(response, chunks)

    # ================= STREAM =================
    async def generate_stream(self, query: str):
        chunks = self.retriever.retrieve(query)

        if not chunks:
            yield "No relevant information found."
            return

        context = "\n".join(chunks)

        full_response = ""

        async for token in self.llm.generate_stream(
            TaskType.RAG, query, context=context
        ):
            full_response += token

        grounded = self._enforce_strict_rag(full_response, chunks)

        for word in grounded.split(" "):
            yield word + " "
            await asyncio.sleep(0.03)

    # ================= ENFORCEMENT =================
    def _enforce_strict_rag(self, response: str, chunks: List[str]) -> str:
        response = (response or "").strip()

        if not chunks:
            return "No relevant information found."

        # exact containment
        for chunk in chunks:
            if response and response in chunk:
                return response

        # best match fallback
        return chunks[0]

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
