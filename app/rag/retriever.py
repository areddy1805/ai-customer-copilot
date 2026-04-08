from typing import List
from app.embeddings.provider_factory import get_embedding_provider
from services.search.provider_factory import get_search_provider


class Retriever:
    def __init__(self, top_k: int = 3):
        self.embedding_provider = get_embedding_provider()
        self.search_provider = get_search_provider()
        self.top_k = top_k

    async def retrieve(self, query: str) -> List[str]:
        query_embedding = await self.embedding_provider.embed(query)

        results = self.search_provider.search(
            query=query, embedding=query_embedding, k=self.top_k
        )

        documents = [r["content"] for r in results]
        metadatas = [{"source": r.get("source")} for r in results]

        return self._build_chunks(documents, metadatas)

    def _build_chunks(self, documents: List[str], metadatas: List[dict]) -> List[str]:
        chunks = []

        for doc, meta in zip(documents, metadatas):
            if not doc:
                continue

            chunks.append(doc.strip())

        return chunks
