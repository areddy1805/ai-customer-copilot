from app.core.config import settings
from app.core.secrets.factory import get_secret_provider

from app.llm.providers.local_provider import LocalProvider
from app.llm.providers.azure_provider import AzureProvider


def get_llm_provider():

    secret_provider = get_secret_provider()

    if settings.LLM_PROVIDER == "azure":
        return AzureProvider(secret_provider=secret_provider)

    return LocalProvider()
