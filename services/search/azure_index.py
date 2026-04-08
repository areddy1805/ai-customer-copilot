from dotenv import load_dotenv

load_dotenv()

from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from azure.core.credentials import AzureKeyCredential
import os


def create_index():

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    key = os.getenv("AZURE_SEARCH_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX")

    client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    fields = [
        SimpleField(name="id", type="Edm.String", key=True),
        SearchableField(name="content", type="Edm.String"),
        SimpleField(name="source", type="Edm.String", filterable=True),
        SearchField(
            name="embedding",
            type="Collection(Edm.Single)",
            searchable=True,
            retrievable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[
            VectorSearchProfile(
                name="vector-profile", algorithm_configuration_name="hnsw"
            )
        ],
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

    client.create_index(index)
