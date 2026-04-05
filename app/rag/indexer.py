from app.rag.loader import DocumentLoader
from app.rag.chunker import DocumentChunker
from app.embeddings.provider_factory import get_embedding_provider
from app.rag.vector_store import VectorStore


class Indexer:
    def __init__(self):
        self.loader = DocumentLoader()
        self.chunker = DocumentChunker()
        self.provider = get_embedding_provider()
        self.store = VectorStore()

    async def run(self):
        documents = self.loader.load_documents()

        chunks = self.chunker.chunk_documents(documents)

        texts = [c["content"] for c in chunks]

        embeddings = await self.provider.embed_batch(texts)

        self.store.reset()

        self.store.add_documents(chunks, embeddings)
