class Step:
    def __init__(self, action: str, params: dict):
        self.action = action
        self.params = params

    def __repr__(self):
        return f"{self.action}({self.params})"


class Plan:
    def __init__(self, steps, query=""):
        self.steps = steps
        self.query = query
