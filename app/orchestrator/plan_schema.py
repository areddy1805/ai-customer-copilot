from typing import List, Optional


ALLOWED_ACTIONS = {"tool", "respond"}


class Step:
    def __init__(
        self,
        step_id: int,
        action: str,
        tool_name: Optional[str] = None,
        input_data: Optional[dict] = None,
        depends_on: Optional[List[int]] = None,
    ):
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Invalid action")

        self.step_id = step_id
        self.action = action
        self.tool_name = tool_name
        self.input = input_data or {}
        self.depends_on = depends_on or []


class Plan:
    def __init__(self, steps, query, trace_id=None):
        self.steps = steps
        self.query = query
        self.trace_id = trace_id
