import asyncio
from app.embeddings.provider_factory import get_embedding_provider
from app.core.bootstrap import load_environment

load_environment()


async def main():
    provider = get_embedding_provider()

    emb = await provider.embed("refund policy timeline")

    print(len(emb))
    print(emb[:5])


asyncio.run(main())
