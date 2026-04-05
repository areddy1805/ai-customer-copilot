from typing import List
from app.embeddings.provider import EmbeddingProvider
from app.rag.embedder import Embedder


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.embedder = Embedder()

    async def embed(self, text: str) -> List[float]:
        return self.embedder.embed_query(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return self.embedder.embed_texts(texts)
