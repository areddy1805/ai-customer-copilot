from app.rag.loader import DocumentLoader
from app.rag.chunker import DocumentChunker
from app.embeddings.provider_factory import get_embedding_provider
from services.search.provider_factory import get_search_provider


class Indexer:
    def __init__(self):
        self.loader = DocumentLoader()
        self.chunker = DocumentChunker()
        self.embedding_provider = get_embedding_provider()
        self.search_provider = get_search_provider()

    async def run(self):
        documents = self.loader.load_documents()

        chunks = self.chunker.chunk_documents(documents)

        texts = [c["content"] for c in chunks]

        embeddings = await self.embedding_provider.embed_batch(texts)

        formatted_docs = []

        for i, chunk in enumerate(chunks):
            formatted_docs.append(
                {
                    "id": str(i),
                    "content": chunk["content"],
                    "source": chunk.get("metadata", {}).get("source", "unknown"),
                    "embedding": embeddings[i],
                }
            )

        print("TOTAL DOCS:", len(formatted_docs))

        self.search_provider.index(formatted_docs)
