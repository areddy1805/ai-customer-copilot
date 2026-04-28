import json
import time
import requests
from collections import Counter

API_URL = "http://127.0.0.1:8000/api/chat"

DATASET_PATH = "app/eval/dataset.json"
RESULTS_PATH = "app/eval/results.json"


def call_api(query: str):
    start = time.time()

    response = requests.post(
        API_URL,
        json={"query": query, "session_id": "eval"},
    )

    latency = int((time.time() - start) * 1000)

    try:
        data = response.json()
    except Exception:
        data = {}

    return data, latency


def extract_tool(response_json):
    if not isinstance(response_json, dict):
        return []

    metrics = response_json.get("metrics", {})
    tools = metrics.get("tools_used", [])

    if tools:
        return sorted(tools)

    details = response_json.get("details", [])
    if details:
        tool = details[0].get("type")
        if tool:
            return [tool]

    return []


def normalize_tool_set(tool):
    if not tool:
        return set()

    if isinstance(tool, list):
        return set(tool)

    if isinstance(tool, str):
        return set(tool.split("+"))

    return set()


def keyword_match(response_text: str, keywords: list):
    if not response_text:
        return 0

    response_text = response_text.lower()

    for kw in keywords:
        if kw.lower() in response_text:
            return 1

    return 0


def classify_failure(result, expected_set):
    metrics = result.get("response", {}).get("metrics", {})

    if metrics.get("error") == "rate_limit":
        return "tool_failure"

    actual_set = normalize_tool_set(result.get("actual_tool"))

    if not actual_set:
        return "planning_failure"

    if actual_set != expected_set:
        if "rag" in actual_set and expected_set != {"rag"}:
            return "retrieval_failure"
        return "planning_failure"

    return "none"


def run_eval():
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)

    results = []

    tool_correct_total = 0
    keyword_correct_total = 0

    for item in dataset:
        query = item["query"]

        response_json, latency = call_api(query)

        actual_tool = extract_tool(response_json)
        expected_tool = item["expected_tool"]

        actual_set = normalize_tool_set(actual_tool)
        expected_set = normalize_tool_set(expected_tool)

        tool_score = 1 if actual_set == expected_set else 0
        tool_correct_total += tool_score

        response_text = response_json.get("response", "")
        keywords = item.get("expected_keywords", [])

        keyword_score = keyword_match(response_text, keywords)
        keyword_correct_total += keyword_score

        result = {
            "id": item["id"],
            "query": query,
            "expected_tool": expected_tool,
            "actual_tool": actual_tool,
            "tool_correct": tool_score,
            "keyword_match": keyword_score,
            "latency": latency,
            "response": response_json,
            "latency_breakdown": response_json.get("trace", {}),
        }

        failure = classify_failure(result, expected_set)
        result["failure_type"] = failure

        results.append(result)

        print(
            f"{item['id']} | tool: {actual_tool} | correct: {tool_score} | {latency} ms"
        )

        # throttle
        if response_json.get("metrics", {}).get("error") == "rate_limit":
            time.sleep(3)
        else:
            time.sleep(1.2)

    total = len(results)

    # -------- FAILURE BREAKDOWN --------
    failure_counts = Counter(r["failure_type"] for r in results)

    print("\n=== FAILURE BREAKDOWN ===")
    for k, v in failure_counts.items():
        pct = (v / total) * 100
        print(f"{k}: {v} ({pct:.2f}%)")

    # -------- LATENCY DISTRIBUTION --------
    planner_total = 0
    decomposer_total = 0
    executor_total = 0
    count_with_latency = 0

    for r in results:
        lb = r.get("latency_breakdown", {})
        if not lb:
            continue

        planner_total += sum(lb.get("planner_ms", []))
        decomposer_total += lb.get("decomposer_ms", 0)
        executor_total += sum(lb.get("executor_ms", []))
        count_with_latency += 1

    if count_with_latency > 0:
        planner_avg = planner_total / count_with_latency
        decomposer_avg = decomposer_total / count_with_latency
        executor_avg = executor_total / count_with_latency

        total_avg = planner_avg + decomposer_avg + executor_avg

        print("\n=== LATENCY DISTRIBUTION ===")
        print(f"Planner: {(planner_avg/total_avg)*100:.2f}%")
        print(f"Decomposer: {(decomposer_avg/total_avg)*100:.2f}%")
        print(f"Executor: {(executor_avg/total_avg)*100:.2f}%")

    # -------- FINAL METRICS --------
    tool_acc = (tool_correct_total / total) * 100
    keyword_acc = (keyword_correct_total / total) * 100

    print("\n=== FINAL METRICS ===")
    print(f"Total: {total}")
    print(f"Tool Accuracy: {tool_acc:.2f}%")
    print(f"Keyword Accuracy: {keyword_acc:.2f}%")

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved results to {RESULTS_PATH}")


if __name__ == "__main__":
    run_eval()
