from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
import os

from services.search.search_provider import SearchProvider

load_dotenv()


class AzureSearchProvider(SearchProvider):

    def __init__(self):
        self.client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
        )

    def search(self, query: str, embedding: list, k: int = 5):

        results = self.client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(
                    vector=embedding, k_nearest_neighbors=k, fields="embedding"
                )
            ],
            top=k,
        )

        return [
            {"content": doc["content"], "source": doc.get("source")} for doc in results
        ]

    def index(self, documents: list):
        result = self.client.upload_documents(documents)

        print("DOC COUNT:", len(documents))
