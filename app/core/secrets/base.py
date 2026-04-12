from abc import ABC, abstractmethod


class SecretProvider(ABC):

    @abstractmethod
    def get_secret(self, key: str) -> str:
        pass
