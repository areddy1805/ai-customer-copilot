# Failure Modes

## 1. Planning Failure

**Definition**
System fails to select correct tool or produces no tool.

**Cause**
- Weak intent classification
- Missing rules / decomposition errors
- Ambiguous query without fallback

**Detection**
- actual_tool != expected_tool
- actual_tool = []

**Example**
"Refund rules for damaged product" → classified as refund_request instead of rag

**Mitigation**
- Rule-based overrides for high-confidence intents
- Intent-aware guards
- RAG fallback for missing structured inputs


---

## 2. Retrieval Failure

**Definition**
RAG returns incorrect / irrelevant information.

**Cause**
- Poor embeddings
- Bad chunking
- Missing documents
- Weak similarity search

**Detection**
- keyword_match = 0
- tool_correct = 1 but response incorrect

**Example**
Policy question returns unrelated answer

**Mitigation**
- Improve chunking strategy
- Add metadata filtering
- Re-rank retrieved documents


---

## 3. Tool Failure

**Definition**
Tool executes but returns failure or error.

**Cause**
- Invalid inputs (e.g., order not delivered)
- Downstream system issues
- API/database errors

**Detection**
- response.status = "failed"
- metrics.error present

**Example**
Refund fails because order not delivered

**Mitigation**
- Input validation before execution
- Retry mechanisms
- Graceful fallback messaging


---

## 4. System Failure

**Definition**
Infrastructure or orchestration breakdown.

**Cause**
- Rate limiting
- Guard blocks
- Timeout / crash
- Circuit breaker activation

**Detection**
- error in ["rate_limit", "guard_block"]
- fallback_triggered = True

**Example**
Too many requests → blocked

**Mitigation**
- Backoff + retry
- Circuit breaker tuning
- Request throttling


---

## 5. Latency Failure

**Definition**
System responds correctly but exceeds acceptable latency.

**Cause**
- Slow RAG retrieval
- Heavy tool execution
- External dependencies

**Detection**
- total_time_ms > threshold
- executor_ms dominant

**Example**
RAG queries taking 3–4 seconds

**Mitigation**
- Caching (semantic + response)
- Index optimization
- Async parallel execution


---

## Summary Table

| Failure Type       | Layer        | Primary Metric    |
|------------------|-------------|----------------------|
| Planning Failure | Orchestrator | tool_correct        |
| Retrieval Failure| RAG         | keyword_match        |
| Tool Failure     | Tools       | error / status       |
| System Failure   | Infra       | fallback / error     |
| Latency Failure  | Performance | total_time_ms        |