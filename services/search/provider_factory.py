from app.core.config import settings
from app.core.secrets.factory import get_secret_provider

from services.search.azure_search_provider import AzureSearchProvider
from services.search.faiss_provider import FAISSProvider
from app.rag.vector_store import VectorStore


def get_search_provider():

    provider = settings.SEARCH_PROVIDER
    print("SEARCH PROVIDER:", provider)

    if provider == "azure":
        secret_provider = get_secret_provider()

        return AzureSearchProvider(secret_provider=secret_provider)

    return FAISSProvider(VectorStore())
