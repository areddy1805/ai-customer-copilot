from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from app.core.secrets.base import SecretProvider


class KeyVaultSecretProvider(SecretProvider):

    KEY_MAP = {
        "AZURE_OPENAI_API_KEY": "azure-openai-api-key",
        "AZURE_OPENAI_ENDPOINT": "azure-openai-endpoint",
        "AZURE_OPENAI_DEPLOYMENT": "azure-openai-deployment",
        "AZURE_EMBEDDING_DEPLOYMENT": "azure-embedding-deployment",
        "AZURE_SEARCH_ENDPOINT": "azure-search-endpoint",
        "AZURE_SEARCH_KEY": "azure-search-key",
        "AZURE_SEARCH_INDEX": "azure-search-index",
    }

    def __init__(self, vault_url: str):
        self.client = SecretClient(
            vault_url=vault_url, credential=DefaultAzureCredential()
        )
        self.cache = {}

    def get_secret(self, key: str) -> str:

        mapped_key = self.KEY_MAP.get(key, key)

        if mapped_key in self.cache:
            return self.cache[mapped_key]

        value = self.client.get_secret(mapped_key).value

        if not value:
            raise ValueError(f"Missing secret in Key Vault: {mapped_key}")

        self.cache[mapped_key] = value
        return value
