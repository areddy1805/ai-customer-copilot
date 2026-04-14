Run these exact tests. Each isolates one failure mode.

⸻

1. SINGLE TOOL (BASELINE)

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "track ORD3",
  "session_id": "t1",
  "debug": true
}'

Expected:

Order ORD3 is delivered.


⸻

2. PURE RAG

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "refund policy",
  "session_id": "t2",
  "debug": true
}'

Expected:

Clean policy answer (no tool contamination)


⸻

3. MULTI-INTENT (CURRENT FAILURE CASE)

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "refund policy and track ORD3",
  "session_id": "t3",
  "debug": true
}'

Expected:

Order ORD3 is delivered. Refund policy: ...

Current bug:

"Unable to process request." prefix


⸻

4. REFUND FLOW (CHAIN DEPENDENCY)

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "refund ORD3",
  "session_id": "t4",
  "debug": true
}'

Expected:

Order → Refund executed in sequence


⸻

5. INVALID ORDER

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "track ORD9999",
  "session_id": "t5",
  "debug": true
}'

Expected:

Order not found.


⸻

6. MIXED FAILURE + SUCCESS

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "refund policy and track ORD9999",
  "session_id": "t6",
  "debug": true
}'

Expected:

Order not found. Refund policy: ...


⸻

7. HALLUCINATION TRAP

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "refund policy and refund ORD3",
  "session_id": "t7",
  "debug": true
}'

Expected:

RAG + order + refund (correct order_id only)

Watch for:

Wrong order_id leakage (ORD123 bug)


⸻

8. DECOMPOSER FAILURE FALLBACK

curl -X POST "http://127.0.0.1:8000/api/chat" \
-H "Content-Type: application/json" \
-d '{
  "query": "track ORD3 and also tell me policy and also something random",
  "session_id": "t8",
  "debug": true
}'

Expected:

Max 3 tasks, stable output


⸻

WHAT THIS VALIDATES

1. Tool correctness
2. RAG isolation
3. Multi-intent merge
4. Planner correctness
5. Error handling
6. Decomposer stability
7. No cross-task leakage


⸻

Run all.
Identify failures.

Then proceed to Step 1 fix (planner isolation).