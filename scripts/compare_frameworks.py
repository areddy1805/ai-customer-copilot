import subprocess
import time
import json

TEST_QUERIES = [
    "Track ORD1",
    "Track ORD1 and refund ORD2",
    "What is refund policy",
]


# --------------------------
# PROCESS-ISOLATED RUNNER (ROBUST)
# --------------------------
def run_subprocess(mode: str, query: str):
    start = time.time()

    result = subprocess.run(
        [
            "python",
            "-m",
            "scripts.run_single",
            mode,
            query,
        ],
        capture_output=True,
        text=True,
    )

    duration = time.time() - start

    stdout = result.stdout.strip()

    # Extract LAST valid JSON line (ignore logs/noise)
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            output = json.loads(line)
            return output["response"], duration

    raise ValueError(f"No valid JSON found. Output was:\n{stdout}")


# --------------------------
# BENCHMARK
# --------------------------
def benchmark():
    results = []

    for query in TEST_QUERIES:
        print(f"\nQUERY: {query}")

        core_res, core_time = run_subprocess("core", query)
        lc_res, lc_time = run_subprocess("langchain", query)
        lg_res, lg_time = run_subprocess("langgraph", query)
        ag_res, ag_time = run_subprocess("autogen", query)

        results.append(
            {
                "query": query,
                "core": (core_res, core_time),
                "langchain": (lc_res, lc_time),
                "langgraph": (lg_res, lg_time),
                "autogen": (ag_res, ag_time),
            }
        )

    return results


# --------------------------
# OUTPUT
# --------------------------
def print_results(results):
    for r in results:
        print("\n==============================")
        print(f"QUERY: {r['query']}")

        for k in ["core", "langchain", "langgraph", "autogen"]:
            res, t = r[k]
            print(f"{k.upper():10} | {t:.3f}s | {res}")


# --------------------------
# ENTRYPOINT
# --------------------------
if __name__ == "__main__":
    results = benchmark()
    print_results(results)
