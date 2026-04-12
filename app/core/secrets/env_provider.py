import os
from .base import SecretProvider


class EnvSecretProvider(SecretProvider):

    def get_secret(self, key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing secret: {key}")
        return value
