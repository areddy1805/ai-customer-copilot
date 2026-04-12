class Step:
    def __init__(
        self,
        action: str,
        params: dict = None,
        step_id: int = None,
        depends_on: list = None,
    ):
        self.action = action
        self.params = params or {}
        self.step_id = step_id
        self.depends_on = depends_on or []

    def __repr__(self):
        return f"{self.step_id}:{self.action}({self.params}) -> deps:{self.depends_on}"


class Plan:
    def __init__(self, steps, query=""):
        self.steps = steps
        self.query = query
