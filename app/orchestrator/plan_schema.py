from typing import List

ALLOWED_ACTIONS = {"get_order", "process_refund", "create_ticket", "fallback_rag"}


class Step:
    def __init__(self, action: str, input_data: dict):
        if action not in ALLOWED_ACTIONS:
            raise ValueError("Invalid action")

        self.action = action
        self.imput = input_data


class Plan:
    def __init__(self, steps: List[Step], query: str):
        self.steps = steps
        self.query = query
