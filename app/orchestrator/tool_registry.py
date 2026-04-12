class ToolRegistry:

    def __init__(self):
        self.tools = {}

    def register(self, name: str, tool_callable):
        self.tools[name] = tool_callable

    def get(self, name: str):
        tool = self.tools.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return tool

    def list_tools(self):
        return list(self.tools.keys())
