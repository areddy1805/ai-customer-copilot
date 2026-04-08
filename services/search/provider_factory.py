import os
from dotenv import load_dotenv

load_dotenv()

from services.search.azure_search_provider import AzureSearchProvider
from services.search.faiss_provider import FAISSProvider
from app.rag.vector_store import VectorStore


def get_search_provider():

    provider = os.getenv("SEARCH_PROVIDER", "local")
    print("SEARCH PROVIDER:", provider)

    if provider == "azure":
        return AzureSearchProvider()
    else:
        return FAISSProvider(VectorStore())
