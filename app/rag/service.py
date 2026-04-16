from typing import List
import asyncio

from app.rag.retriever import Retriever
from app.llm.service import LLMService
from app.llm.models import TaskType


class RAGService:
    def __init__(self, llm: LLMService):
        self.retriever = Retriever()
        self.llm = llm

    # ================= NON-STREAM =================
    async def generate(self, query: str) -> str:
        chunks = await self.retriever.retrieve(query)

        if not chunks:
            return "No relevant information found."

        context = "\n".join(chunks)

        # -------- BUILD PROMPT (CRITICAL) --------
        prompt = f"""
You must answer ONLY using the provided context.

Context:
{context}

Query:
{query}
"""

        # -------- CORRECT LLM CALL --------
        response = await self.llm.generate(
            prompt=prompt,
            temperature=0,
            task=TaskType.RAG,
        )

        return response.strip()

    # ================= STREAM =================
    async def generate_stream(self, query: str):
        chunks = await self.retriever.retrieve(query)

        if not chunks:
            yield "No relevant information found."
            return

        context = "\n".join(chunks)

        prompt = f"""
You must answer ONLY using the provided context.

Context:
{context}

Query:
{query}
"""

        async for token in self.llm.generate_stream(
            prompt=prompt,
            temperature=0,
            task=TaskType.RAG,
        ):
            yield token
            await asyncio.sleep(0.01)
