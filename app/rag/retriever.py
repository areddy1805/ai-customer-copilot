from typing import List
from app.rag.embedder import Embedder
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, top_k: int = 3):
        self.embedder = Embedder()
        self.store = VectorStore()
        self.top_k = top_k

    def retrieve(self, query: str) -> List[str]:
        """
        Retrieve relevant context as list of clean chunks
        """

        query_embedding = self.embedder.embed_query(query)

        results = self.store.query(query_embedding=query_embedding, top_k=self.top_k)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        return self._build_chunks(documents, metadatas)

    def _build_chunks(self, documents: List[str], metadatas: List[dict]) -> List[str]:
        """
        Return clean chunks (no metadata pollution)
        """

        chunks = []

        for doc, meta in zip(documents, metadatas):
            if not doc:
                continue

            chunks.append(doc.strip())

        return chunks
