# Failure Modes — AI Customer Copilot

## 1. retrieval_failure

Definition
System fails to fetch correct external or knowledge data.

Cause
- RAG returns irrelevant or empty results
- Embedding mismatch
- Search provider failure

Detection
- tool = rag
- response irrelevant OR empty
- keyword_match = 0

Mitigation
- improve chunking / embeddings
- increase top-k
- fallback to LLM summary

---

## 2. planning_failure

Definition
Planner generates incorrect or incomplete execution plan.

Cause
- wrong tool selection
- missing required parameters (order_id)
- invalid step sequence

Detection
- tool_correct = 0
- plan_validator modifies or rejects plan

Mitigation
- stricter plan validation
- better prompt constraints
- add rule-based overrides

---

## 3. tool_failure

Definition
Tool execution fails after correct planning.

Cause
- backend logic failure
- invalid state (e.g., refund before delivery)
- exception during execution

Detection
- result.status = "failed"
- metrics.error present
- fallback_triggered = true

Mitigation
- retries
- better error handling
- circuit breakers

---

## 4. guard_failure

Definition
Request blocked before processing.

Cause
- empty input
- policy violation

Detection
- error = "guard_block"
- no tools executed

Mitigation
- better user prompts
- clearer validation messages

---

## 5. unknown

Definition
Failure does not match known categories.

Cause
- unexpected system behavior

Detection
- default fallback classification

Mitigation
- log and analyze manually

---