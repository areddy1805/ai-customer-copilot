from typing import List
from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model
        """
        self.model = SentenceTransformer(model_name)
        self.cache = {}

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Convert list of texts into embeddings
        """
        embeddings = self.model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )

        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        key = query.strip().lower()

        if key in self.cache:
            return self.cache[key]

        embedding = self.model.encode(
            query, convert_to_numpy=True, normalize_embeddings=True
        ).tolist()

        self.cache[key] = embedding

        if len(self.cache) > 1000:
            self.cache.pop(next(iter(self.cache)))

        return embedding
