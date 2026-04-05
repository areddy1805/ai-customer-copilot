import chromadb
from chromadb.config import Settings
from typing import List, Dict


class VectorStore:
    def __init__(self, persist_dir: str = "data/chroma"):
        """
        Initialize ChromaDB client
        """
        self.client = chromadb.PersistentClient(path=persist_dir)

        self.collection = self.client.get_or_create_collection(name="knowledge_base")

    def add_documents(self, chunks: List[Dict], embeddings: List[List[float]]):
        """
        Store chunks with embeddings
        """
        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk["metadata"]["chunk_id"])
            documents.append(chunk["content"])
            metadatas.append(chunk["metadata"])

        self.collection.add(
            ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
        )

    def query(self, query_embedding: List[float], top_k: int = 3):
        """
        Retrieve similar documents
        """
        results = self.collection.query(
            query_embeddings=[query_embedding], n_results=top_k
        )

        return results

    def reset(self):
        """
        Clear entire collection safely
        """
        self.client.delete_collection("knowledge_base")
        self.collection = self.client.get_or_create_collection(name="knowledge_base")
