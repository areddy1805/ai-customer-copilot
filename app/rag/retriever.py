from typing import List
from app.embeddings.provider_factory import get_embedding_provider
from app.rag.vector_store import VectorStore


class Retriever:
    def __init__(self, top_k: int = 3):
        self.embedding_provider = get_embedding_provider()
        self.store = VectorStore()
        self.top_k = top_k

    async def retrieve(self, query: str) -> List[str]:
        query_embedding = await self.embedding_provider.embed(query)

        results = self.store.query(query_embedding=query_embedding, top_k=self.top_k)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        return self._build_chunks(documents, metadatas)

    def _build_chunks(self, documents: List[str], metadatas: List[dict]) -> List[str]:
        chunks = []

        for doc, meta in zip(documents, metadatas):
            if not doc:
                continue

            chunks.append(doc.strip())

        return chunks
