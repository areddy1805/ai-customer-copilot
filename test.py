from app.orchestrator.orchestrator import Orchestrator
import time
import threading
from uuid import uuid4


# ================= HELPERS =================
def new_orch():
    return Orchestrator()


# ================= BASIC TEST =================
def test_basic():
    print("\n=== BASIC TEST ===")
    orch = new_orch()

    queries = [
        "Hello",
        "Where is my order ORD1?",
        "What is refund policy?",
        "I want a refund for ORD2",
        "random question about system",
    ]

    for q in queries:
        print(f"\nQuery: {q}")
        res = orch.run(q, str(uuid4()))
        print("Response:", res.final_response)


# ================= STREAM TEST =================
def test_stream():
    print("\n=== STREAM TEST ===")
    orch = new_orch()

    queries = [
        "Hello",
        "Where is my order ORD1?",
        "What is refund policy?",
    ]

    for q in queries:
        print(f"\nQuery: {q}")
        print("Response:", end=" ")

        for t in orch.run_stream(q, str(uuid4())):
            print(t, end="", flush=True)

        print("\n")


# ================= CACHE TEST =================
def test_cache():
    print("\n=== CACHE TEST ===")
    orch = new_orch()

    session = str(uuid4())
    q = "What is refund policy?"

    print("\nFirst call (MISS)")
    print(orch.run(q, session).final_response)

    print("\nSecond call (HIT)")
    print(orch.run(q, session).final_response)


# ================= SEMANTIC CACHE TEST =================
def test_semantic_cache():
    print("\n=== SEMANTIC CACHE TEST ===")
    orch = new_orch()

    session = str(uuid4())
    q1 = "What is refund policy?"
    q2 = "Tell me refund rules"

    print("\nFirst query:")
    print(orch.run(q1, session).final_response)

    print("\nSimilar query:")
    print(orch.run(q2, session).final_response)


# ================= TOOL TEST =================
def test_tool():
    print("\n=== TOOL TEST ===")
    orch = new_orch()

    queries = [
        "Where is my order ORD1?",
        "Refund status for ORD2",
        "Create ticket for order ORD3 issue",
    ]

    for q in queries:
        print(f"\nQuery: {q}")
        print(orch.run(q, str(uuid4())).final_response)


# ================= MULTI-STEP TEST =================
def test_multistep():
    print("\n=== MULTI-STEP TEST ===")
    orch = new_orch()

    q = "I ordered something but want refund status for ORD2"
    print("Query:", q)
    print("Response:", orch.run(q, str(uuid4())).final_response)


# ================= CONCURRENCY TEST =================
def test_concurrency():
    print("\n=== CONCURRENCY TEST ===")
    orch = new_orch()

    def worker(i):
        res = orch.run(f"Hello {i}", str(uuid4()))
        print(f"Thread {i}: {res.final_response}")

    threads = []

    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()


# ================= EDGE CASE TEST =================
def test_edge_cases():
    print("\n=== EDGE CASE TEST ===")
    orch = new_orch()

    queries = [
        "",
        "ORD999999",
        "talk to human",
        "@@@@@####",
    ]

    for q in queries:
        print(f"\nQuery: {q}")
        print("Response:", orch.run(q, str(uuid4())).final_response)


# ================= MAIN =================
if __name__ == "__main__":
    start = time.time()

    test_basic()
    test_stream()
    test_cache()
    test_semantic_cache()
    test_tool()
    test_multistep()
    test_concurrency()
    test_edge_cases()

    end = time.time()
    print(f"\nTotal test time: {int(end - start)}s")
