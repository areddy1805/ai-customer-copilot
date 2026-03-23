from typing import List
from sentence_transformers import SentenceTransformer


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding model
        """
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Convert list of texts into embeddings
        """
        embeddings = self.model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True
        )

        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """
        Convert single query into embedding
        """
        embedding = self.model.encode(
            query, convert_to_numpy=True, normalize_embeddings=True
        )

        return embedding.tolist()
