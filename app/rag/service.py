from app.rag.retriever import Retriever
from app.llm.service import LLMService
from app.llm.models import TaskType


class RAGService:
    def __init__(self):
        self.retriever = Retriever()
        self.llm = LLMService()

    def generate(self, query: str) -> str:
        """
        Full RAG pipeline:
        query → retrieve → generate grounded response
        """

        context = self.retriever.retrieve(query)

        response = self.llm.generate(task=TaskType.RAG, query=query, context=context)

        return response
