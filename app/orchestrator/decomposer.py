import re


class Decomposer:
    def decompose(self, query: str, context: str = ""):
        """
        Splits multi-intent queries into atomic tasks
        """

        # Split on conjunctions
        parts = re.split(r"\band\b|\bthen\b|,", query.lower())

        tasks = [p.strip() for p in parts if p.strip()]

        return tasks if len(tasks) > 1 else [query]
