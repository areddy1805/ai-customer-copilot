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
                "plan": state.metadata.get("plans"),
            }

            result["pass"] = self._evaluate(item, result)

            results.append(result)

        return results

    def _evaluate(self, expected, actual):

        # intent check
        if "expected_intent" in expected:
            # allow flexible intent
            if expected["expected_intent"] is not None:
                if actual.get("intent") != expected["expected_intent"]:
                    return False

        # content check
        if "expected_contains" in expected:
            response = actual.get("response") or ""

            if not response:
                return False

            if "expected_contains" in expected and expected["expected_contains"]:
                if expected["expected_contains"].lower() not in response.lower():
                    return False

        # route check
        if "expected_route" in expected:
            metadata = actual.get("metadata") or {}

            if metadata.get("route") != expected["expected_route"]:
                return False

        # plan check
        if "expected_plan" in expected:
            if actual.get("plan") != expected["expected_plan"]:
                return False

        return True
