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


def classify_failure(r, expected_tool):
    metrics = r.get("response", {}).get("metrics", {})
    error = metrics.get("error", "")

    actual = r.get("actual_tool", [])

    if error in ["guard_block", "rate_limit"]:
        return "tool_failure"

    actual_set = normalize_tool_set(actual)
    expected_set = normalize_tool_set(expected_tool)

    if not actual_set:
        return "planning_failure"

    if actual_set != expected_set:
        return "planning_failure"

    return "none"


def run_eval():
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)

    results = []

    tool_correct_total = 0
    keyword_correct_total = 0

    fallback_count = 0
    retry_total = 0
    tool_failures = 0

    # -------- AGGREGATION --------
    planner_sum = 0
    decomposer_sum = 0
    executor_sum = 0
    total_sum = 0
    latency_count = 0
    cache_hits = 0

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

        metrics = response_json.get("metrics", {})

        if metrics.get("cache_hit"):
            cache_hits += 1

        if metrics.get("fallback_triggered"):
            fallback_count += 1

        retry_total += metrics.get("retry_count", 0)

        if metrics.get("error"):
            tool_failures += 1

        latency_breakdown = response_json.get("latency_breakdown", {})

        # -------- LATENCY AGGREGATION --------
        if latency_breakdown:
            planner = sum(latency_breakdown.get("planner_ms", []))
            decomposer = latency_breakdown.get("decomposer_ms", 0)
            executor = sum(latency_breakdown.get("executor_ms", []))
            total_time = latency_breakdown.get("total_time_ms", 0)

            if total_time > 0:
                planner_sum += planner
                decomposer_sum += decomposer
                executor_sum += executor
                total_sum += total_time
                latency_count += 1

        result = {
            "id": item["id"],
            "query": query,
            "expected_tool": expected_tool,
            "actual_tool": actual_tool,
            "tool_correct": tool_score,
            "keyword_match": keyword_score,
            "latency": latency,
            "response": response_json,
            "latency_breakdown": latency_breakdown,
        }

        failure = classify_failure(result, expected_tool)
        result["failure_type"] = failure

        results.append(result)

        print(
            f"{item['id']} | tool: {actual_tool} | correct: {tool_score} | {latency} ms"
        )

        if response_json.get("metrics", {}).get("error") == "rate_limit":
            time.sleep(3)
        else:
            time.sleep(1.2)

    total = len(results)

    tool_acc = (tool_correct_total / total) * 100
    keyword_acc = (keyword_correct_total / total) * 100

    print("\n=== AGGREGATE SCORES ===")
    print(f"Tool Accuracy: {tool_acc:.2f}%")
    print(f"Keyword Match Rate: {keyword_acc:.2f}%")

    type_stats = {}

    for r, item in zip(results, dataset):
        t = item["type"]

        if t not in type_stats:
            type_stats[t] = {"count": 0, "tool_correct": 0, "keyword_correct": 0}

        type_stats[t]["count"] += 1
        type_stats[t]["tool_correct"] += r["tool_correct"]
        type_stats[t]["keyword_correct"] += r["keyword_match"]

    print("\n=== TYPE BREAKDOWN ===")
    for t, stats in type_stats.items():
        t_tool_acc = (stats["tool_correct"] / stats["count"]) * 100
        t_kw_acc = (stats["keyword_correct"] / stats["count"]) * 100

        print(f"{t} → Tool: {t_tool_acc:.2f}% | Keyword: {t_kw_acc:.2f}%")

    failure_counts = Counter(r["failure_type"] for r in results)

    print("\n=== FAILURE BREAKDOWN ===")
    for k, v in failure_counts.items():
        pct = (v / total) * 100
        print(f"{k}: {v} ({pct:.2f}%)")

    # -------- EXISTING LATENCY --------
    planner_total = 0
    decomposer_total = 0
    executor_total = 0
    count_with_latency = 0

    for r in results:
        trace = r.get("latency_breakdown", {})

        if not trace:
            continue

        planner = trace.get("planner_ms", [])
        decomposer = trace.get("decomposer_ms", 0)
        executor = trace.get("executor_ms", [])

        if not planner and not decomposer and not executor:
            continue

        planner_total += sum(planner)
        decomposer_total += decomposer
        executor_total += sum(executor)

        count_with_latency += 1

    if count_with_latency > 0:
        planner_avg = planner_total / count_with_latency
        decomposer_avg = decomposer_total / count_with_latency
        executor_avg = executor_total / count_with_latency

        total_avg = planner_avg + decomposer_avg + executor_avg

        if total_avg > 0:
            print("\n=== LATENCY DISTRIBUTION ===")
            print(f"Planner: {(planner_avg/total_avg)*100:.2f}%")
            print(f"Decomposer: {(decomposer_avg/total_avg)*100:.2f}%")
            print(f"Executor: {(executor_avg/total_avg)*100:.2f}%")

            print("\n=== ABSOLUTE LATENCY (ms) ===")
            print(f"Planner Avg: {planner_avg:.2f}")
            print(f"Decomposer Avg: {decomposer_avg:.2f}")
            print(f"Executor Avg: {executor_avg:.2f}")

            print("\n=== SYSTEM SHARE ===")
            print(f"LLM: {((planner_avg+decomposer_avg)/total_avg)*100:.2f}%")
            print(f"Execution: {(executor_avg/total_avg)*100:.2f}%")

    # -------- AGGREGATED LATENCY --------
    if latency_count > 0:
        avg_planner = planner_sum / latency_count
        avg_decomposer = decomposer_sum / latency_count
        avg_executor = executor_sum / latency_count
        avg_total = total_sum / latency_count

        print("\n=== AGGREGATED LATENCY SHARE ===")
        print(f"Planner: {(avg_planner/avg_total)*100:.2f}%")
        print(f"Decomposer: {(avg_decomposer/avg_total)*100:.2f}%")
        print(f"Executor: {(avg_executor/avg_total)*100:.2f}%")

        print("\n=== AGGREGATED LATENCY (ms) ===")
        print(f"Planner Avg: {avg_planner:.2f}")
        print(f"Decomposer Avg: {avg_decomposer:.2f}")
        print(f"Executor Avg: {avg_executor:.2f}")
        print(f"Total Avg: {avg_total:.2f}")

    # -------- SYSTEM TIME --------
    total_llm = 0
    total_exec = 0
    count = 0

    for r in results:
        m = r.get("response", {}).get("metrics", {})

        llm_time = m.get("llm_ms", 0)
        exec_time = sum(m.get("executor_ms", []))

        if llm_time or exec_time:
            total_llm += llm_time
            total_exec += exec_time
            count += 1

    if count > 0:
        avg_llm = total_llm / count
        avg_exec = total_exec / count
        total_time = avg_llm + avg_exec

        print("\n=== SYSTEM TIME BREAKDOWN ===")
        print(f"LLM: {(avg_llm/total_time)*100:.2f}%")
        print(f"Execution: {(avg_exec/total_time)*100:.2f}%")

    print("\n=== CACHE METRICS ===")
    print(f"Cache Hit Rate: {(cache_hits/total)*100:.2f}%")

    print("\n=== RELIABILITY METRICS ===")
    print(f"Fallback Rate: {(fallback_count/total)*100:.2f}%")
    print(f"Avg Retry Count: {retry_total/total:.2f}")
    print(f"Tool Failure Rate: {(tool_failures/total)*100:.2f}%")

    print("\n=== FINAL METRICS ===")
    print(f"Total: {total}")
    print(f"Tool Accuracy: {tool_acc:.2f}%")
    print(f"Keyword Accuracy: {keyword_acc:.2f}%")

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved results to {RESULTS_PATH}")


if __name__ == "__main__":
    run_eval()
