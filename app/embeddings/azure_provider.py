from typing import List
from openai import AsyncAzureOpenAI
from app.embeddings.provider import EmbeddingProvider
from app.core.config import settings


class AzureEmbeddingProvider(EmbeddingProvider):
    def __init__(self, secret_provider):
        self.secret_provider = secret_provider

        self.client = AsyncAzureOpenAI(
            api_key=self.secret_provider.get_secret("AZURE_OPENAI_API_KEY"),
            azure_endpoint=self.secret_provider.get_secret("AZURE_OPENAI_ENDPOINT"),
            api_version=settings.AZURE_EMBEDDING_API_VERSION,
        )

        self.model = self.secret_provider.get_secret("AZURE_EMBEDDING_DEPLOYMENT")

    async def embed(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]
