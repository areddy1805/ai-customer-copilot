from app.core.config import settings
from app.embeddings.local_provider import LocalEmbeddingProvider
from app.embeddings.azure_provider import AzureEmbeddingProvider


def get_embedding_provider():
    if settings.EMBEDDING_PROVIDER == "azure":
        from app.embeddings.azure_provider import AzureEmbeddingProvider

        return AzureEmbeddingProvider()

    return LocalEmbeddingProvider()
