class SearchProvider:

    def search(self, query: str, embedding: list, k: int = 5):
        raise NotImplementedError

    def index(self, documents: list):
        raise NotImplementedError
