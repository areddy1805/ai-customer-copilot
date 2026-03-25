import numpy as np


class ToolSelector:

    def __init__(self, registry, threshold=0.75):
        self.registry = registry
        self.threshold = threshold

    def select(self, query: str):

        q_emb = np.array(self.registry.embedder.embed_query(query))

        best_tool = None
        best_score = -1

        for tool in self.registry.get_all():
            score = np.dot(q_emb, tool["embedding"])

            if score > best_score:
                best_score = score
                best_tool = tool["name"]

        if best_score >= self.threshold:
            return best_tool

        return None
