from typing import List

from app.rag.retriever import Retriever
from app.llm.service import LLMService
from app.llm.models import TaskType


class RAGService:
    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()

    def generate(self, query: str) -> str:
        """
        Full RAG pipeline:
        query → retrieve → generate grounded response
        """

        context = self.retriever.retrieve(query)

        response = self._enforce_strict_rag(response, context_chunks)

        return response

    def _enforce_strict_rag(self, response: str, context_chunks: List[str]) -> str:
        response = response.strip()

        for chunk in context_chunks:
            if response in chunk:
                return response

        # fallback → force exact chunk
        return context_chunks[0].strip()
