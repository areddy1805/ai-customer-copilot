class FailureAnalyzer:

    def analyze(self, results):

        failures = []

        for r in results:
            if not r["pass"]:
                failures.append(
                    {
                        "query": r["query"],
                        "intent": r["intent"],
                        "response": r["response"],
                        "plan": r["metadata"].get("plans"),
                    }
                )

        return failures
