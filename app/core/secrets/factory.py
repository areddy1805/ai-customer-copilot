from app.core.secrets.env_provider import EnvSecretProvider
from app.core.secrets.keyvault_provider import KeyVaultSecretProvider
from app.core.config import get_settings

settings = get_settings()


def get_secret_provider():
    if settings.SECRET_PROVIDER == "keyvault":
        return KeyVaultSecretProvider(vault_url=settings.AZURE_KEY_VAULT_URL)

    return EnvSecretProvider()
