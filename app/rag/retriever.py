from typing import List
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, top_k: int = 3):
        self.embedder = Embedder()
        self.store = VectorStore()
        self.top_k = top_k

    def retrieve(self, query: str) -> str:
        """
        Retrieve relevant context for a query
        """

        query_embedding = self.embedder.embed_query(query)

        results = self.store.query(query_embedding=query_embedding, top_k=self.top_k)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        context = self._build_context(documents, metadatas)

        return context

    def _build_context(self, documents: List[str], metadatas: List[dict]) -> str:
        """
        Combine retrieved chunks into structured context
        """

        context_parts = []

        for doc, meta in zip(documents, metadatas):
            section = meta.get("section", "unknown")
            source = meta.get("source", "unknown")

            context_parts.append(f"[Source: {source} | Section: {section}]\n{doc}")

        return "\n\n".join(context_parts)
