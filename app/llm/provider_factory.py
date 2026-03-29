from app.core.config import settings
from app.llm.providers.local_provider import LocalProvider
from app.llm.providers.azure_provider import AzureProvider


def get_llm_provider():
    if settings.LLM_PROVIDER == "azure":
        return AzureProvider()
    return LocalProvider()
