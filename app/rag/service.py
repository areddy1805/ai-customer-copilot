from typing import List

from app.rag.retriever import Retriever
from app.llm.service import LLMService
from app.llm.models import TaskType
from app.cache.response_cache import ResponseCache


class RAGService:
    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()
        self.cache = ResponseCache()

    # ================= NON-STREAM =================
    def generate(self, query: str) -> str:
        # -------- CACHE HIT --------
        cached = self.cache.get(query)
        if cached:
            print("RAG CACHE HIT")
            return cached

        chunks = self.retriever.retrieve(query)

        if not chunks:
            return "No relevant information found."

        context = "\n".join(chunks)

        response = self.llm.generate(TaskType.RAG, query, context=context)

        grounded = self._enforce_strict_rag(response, chunks)

        # -------- STORE --------
        self.cache.set(query, grounded)

        return grounded

    # ================= STREAM =================
    def generate_stream(self, query: str):
        # -------- CACHE HIT --------
        cached = self.cache.get(query)
        if cached:
            print("RAG CACHE HIT (STREAM)")
            yield cached
            return

        chunks = self.retriever.retrieve(query)

        if not chunks:
            yield "No relevant information found."
            return

        context = "\n".join(chunks)

        stream = self.llm.generate_stream(TaskType.RAG, query, context=context)

        full_response = ""

        for token in stream:
            full_response += token

        grounded = self._enforce_strict_rag(full_response, chunks)

        # -------- STORE --------
        self.cache.set(query, grounded)

        yield grounded

    # ================= ENFORCEMENT =================
    def _enforce_strict_rag(self, response: str, chunks: List[str]) -> str:
        response = (response or "").strip()

        if not chunks:
            return "No relevant information found."

        for chunk in chunks:
            if response and response in chunk:
                return response

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
