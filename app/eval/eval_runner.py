import asyncio

from app.orchestrator.orchestrator import Orchestrator
from app.eval.eval_dataset import EVAL_QUERIES
from app.eval.evaluator import Evaluator
from app.eval.failure_analyzer import FailureAnalyzer


async def main():
    orch = Orchestrator()

    # disable rate limiter for eval
    orch.rate_limiter.allow = lambda x: True

    evaluator = Evaluator(orch)

    results = []

    for i, item in enumerate(EVAL_QUERIES):
        state = await orch.run(item["query"], f"eval_{i}")  # FIX

        results.append(
            {
                "query": item["query"],
                "intent": state.intent,
                "response": state.final_response,
                "metadata": state.metadata,
                "plan": state.metadata.get("plans"),
                "pass": evaluator._evaluate(
                    item,
                    {
                        "intent": state.intent,
                        "response": state.final_response,
                        "metadata": state.metadata,
                        "plan": state.metadata.get("plans"),
                    },
                ),
            }
        )

    analyzer = FailureAnalyzer()
    failures = analyzer.analyze(results)

    print("\n=== RESULTS ===")
    for r in results:
        print(r["query"], "->", "PASS" if r["pass"] else "FAIL")

    print("\n=== FAILURES ===")
    for f in failures:
        print(f)

    print("\n=== METRICS ===")
    print(orch.metrics.snapshot())


if __name__ == "__main__":
    asyncio.run(main())  # FIX
