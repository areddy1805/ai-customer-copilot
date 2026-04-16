import numpy as np


class SemanticCache:

    def __init__(self, embedder, threshold=0.70, max_size=1000):
        self.embedder = embedder
        self.threshold = threshold
        self.max_size = max_size
        self.store = []  # [(embedding, response)]

    def get(self, query: str):

        if not self.store:
            return None

        q_emb = np.array(self.embedder.embed_query(query))

        best_score = -1
        best_response = None

        for emb, resp in self.store:
            score = np.dot(q_emb, emb)

            if score > best_score:
                best_score = score
                best_response = resp

        if best_score >= self.threshold:
            return best_response

        return None

    def set(self, query: str, response: str):

        # ---- QUALITY FILTER ----
        if (
            not response
            or len(response) < 20
            or "escalated" in response.lower()
            or "something went wrong" in response.lower()
        ):
            return

        emb = np.array(self.embedder.embed_query(query))

        # ---- DEDUP (avoid near-identical embeddings spam) ----
        for existing_emb, _ in self.store:
            if np.dot(emb, existing_emb) > 0.995:
                return

        # ---- EVICTION ----
        if len(self.store) >= self.max_size:
            self.store.pop(0)

        self.store.append((emb, response))
