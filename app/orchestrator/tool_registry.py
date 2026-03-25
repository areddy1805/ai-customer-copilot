class ToolRegistry:

    def __init__(self, embedder):
        self.embedder = embedder
        self.tools = []

    def register(self, name: str, description: str):
        embedding = self.embedder.embed_query(description)

        self.tools.append(
            {"name": name, "description": description, "embedding": embedding}
        )

    def get_all(self):
        return self.tools
