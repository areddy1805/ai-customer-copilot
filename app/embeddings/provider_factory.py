from app.core.config import settings
from app.core.secrets.factory import get_secret_provider

from app.embeddings.local_provider import LocalEmbeddingProvider
from app.embeddings.azure_provider import AzureEmbeddingProvider


def get_embedding_provider():

    secret_provider = get_secret_provider()
    print("SECRET_PROVIDER INSTANCE:", type(secret_provider).__name__)

    if settings.EMBEDDING_PROVIDER == "azure":
        return AzureEmbeddingProvider(secret_provider=secret_provider)

    return LocalEmbeddingProvider()
