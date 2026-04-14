from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.models import VectorizedQuery
import time

from services.search.search_provider import SearchProvider


class AzureSearchProvider(SearchProvider):

    def __init__(self, secret_provider):
        self.client = SearchClient(
            endpoint=secret_provider.get_secret("AZURE_SEARCH_ENDPOINT"),
            index_name=secret_provider.get_secret("AZURE_SEARCH_INDEX"),
            credential=AzureKeyCredential(
                secret_provider.get_secret("AZURE_SEARCH_KEY")
            ),
        )

    # ================= SEARCH =================
    def search(self, query: str, embedding: list, k: int = 5):
        results = self.client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(
                    vector=embedding, k_nearest_neighbors=k, fields="embedding"
                )
            ],
            top=k,
        )

        return [
            {"content": doc["content"], "source": doc.get("source")} for doc in results
        ]

    # ================= INDEX (FIXED) =================
    def index(self, documents: list, batch_size: int = 2):
        total = len(documents)
        print(f"TOTAL DOCS: {total}")

        for i in range(0, total, batch_size):
            batch = documents[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            print(f"INDEXING BATCH {batch_num} ({len(batch)} docs)")

            for attempt in range(3):
                try:
                    result = self.client.upload_documents(batch, timeout=10)

                    failed = [r for r in result if not r.succeeded]

                    if failed:
                        print(f"BATCH {batch_num} FAILED DOCS:", failed)

                    break

                except Exception as e:
                    print(f"BATCH {batch_num} ERROR (attempt {attempt+1}): {str(e)}")

                    if attempt == 2:
                        raise

                    time.sleep(3)

        print("INDEXING COMPLETE")
