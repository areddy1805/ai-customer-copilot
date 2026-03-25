from typing import List


class Step:
    def __init__(self, action: str, input_data: dict):
        self.action = action
        self.input = input_data


class Plan:
    def __init__(self, steps: List[Step], query: str):
        self.steps = steps
        self.query = query
