import time


class Evaluator:

    def __init__(self, orchestrator):
        self.orch = orchestrator

    def run(self, dataset):

        results = []

        for item in dataset:

            start = time.time()

            state = self.orch.run(item["query"], "eval")

            latency = int((time.time() - start) * 1000)

            result = {
                "query": item["query"],
                "intent": state.intent,
                "response": state.final_response,
                "latency": latency,
                "metadata": state.metadata,
            }

            result["pass"] = self._evaluate(item, result)

            results.append(result)

        return results

    def _evaluate(self, expected, actual):

        # intent check
        if "expected_intent" in expected:
            if actual["intent"] != expected["expected_intent"]:
                return False

        # content check
        if "expected_contains" in expected:
            if expected["expected_contains"].lower() not in actual["response"].lower():
                return False

        # route check
        if "expected_route" in expected:
            if actual["metadata"].get("route") != expected["expected_route"]:
                return False

        return True
