from app.orchestrator.orchestrator import Orchestrator
from app.eval.eval_dataset import EVAL_QUERIES
from app.eval.evaluator import Evaluator
from app.eval.failure_analyzer import FailureAnalyzer


orch = Orchestrator()

evaluator = Evaluator(orch)
results = evaluator.run(EVAL_QUERIES)

analyzer = FailureAnalyzer()
failures = analyzer.analyze(results)

print("\n=== RESULTS ===")
for r in results:
    print(r["query"], "->", "PASS" if r["pass"] else "FAIL")

print("\n=== FAILURES ===")
for f in failures:
    print(f)
