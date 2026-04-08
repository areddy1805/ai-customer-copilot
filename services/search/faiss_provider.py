from services.search.search_provider import SearchProvider


class FAISSProvider(SearchProvider):

    def __init__(self, vector_store):
        self.vector_store = vector_store

    def search(self, query: str, embedding: list, k: int = 5):
        results = self.vector_store.query(query_embedding=embedding, top_k=k)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        return [
            {"content": documents[i], "source": metadatas[i].get("source")}
            for i in range(len(documents))
        ]

    def index(self, documents: list):

        chunks = []
        embeddings = []

        for i, d in enumerate(documents):
            chunks.append(
                {
                    "content": d["content"],
                    "metadata": {
                        "source": d.get("source"),
                        "chunk_id": str(i),  # REQUIRED for Chroma
                    },
                }
            )
            embeddings.append(d["embedding"])

        self.vector_store.reset()

        self.vector_store.add_documents(chunks, embeddings)
