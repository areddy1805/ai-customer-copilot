# System Design — Deterministic AI Customer Copilot (v2.0)

## Core Flow

User → Guard → Classifier → Orchestrator →
[Fast Path | Decomposer → Planner] → Execution Graph →
[Tools | RAG] → Composer → Response → Metrics

Aligned with system lifecycle defined in README  [oai_citation:0‡readme.md](sediment://file_0000000099a07207b100a1ea9ded8684)

---

## 1. Control Layer (Pre-Execution)

### Guardrails + Rate Limiter
Blocks unsafe or excessive requests

Failure:
- system_failure

---

### Intent Classifier
Rule-based mapping → intent

Used for:
- routing
- fast-path activation

Tradeoff:
- fast but rigid

Failure:
- planning_failure

---

## 2. Fast Path (Critical Optimization)

### Purpose
Bypass LLM completely for high-confidence queries

### Logic
If:
- order_id present
- keywords match (order/refund/cancel)

Then:
→ Direct Plan Creation (ZERO LLM)

### Impact
- 0 ms planner/decomposer
- deterministic execution
- 100% accuracy for structured queries

Observed in eval:
- LLM usage = 0%
- Execution = 100%

---

## 3. Decomposer (Fallback Only)

### Role
Split multi-intent queries

Example:
"Track and refund order" → 2 tasks

### Trigger
ONLY when fast-path fails

Failure:
- planning_failure

---

## 4. Planner

### Role
Convert task → Plan (Steps)

Plan:
Step(action, params)

### Modes
- Direct (rule-based override)
- LLM-based (fallback)

### Validation
PlanValidator enforces:
- valid tools
- parameter correctness

Failure:
- planning_failure

---

## 5. Execution Graph

### Role
Resolve dependencies + ordering

Example:
order → refund

### Implementation
- ordered_tasks (order first)
- deferred_tasks (refund later)

### Constraint
Bounded loop (MAX_AGENT_STEPS = 2)

Failure:
- wrong sequencing

---

## 6. Execution Layer

### Executor

Runs:
- tools (order, refund, ticket)
- rag

### Features
- parallel execution
- inflight deduplication
- plan cache
- response cache

### Output
Structured tool results

Failure:
- tool_failure

---

## 7. Tool Layer

### Tools
- order
- refund
- ticket

### Properties
- deterministic
- validated inputs
- no LLM dependency

Failure:
- tool_failure (e.g. invalid state)

---

## 8. RAG Layer

### Trigger
Intent = refund_policy / faq

### Flow
query → embed → retrieve → generate

### Behavior
- bypass planner
- direct execution

### Observation
- high latency (~3s)
- dominant bottleneck

Failure:
- retrieval_failure

---

## 9. Response Composer

### Role
Merge tool outputs → final response

### Output
- summary
- structured details

Failure:
- aggregation issues

---

## 10. Observability Layer (NEW)

### Metrics Captured

Per request:
- tool accuracy
- keyword match
- latency breakdown:
  - planner_ms
  - decomposer_ms
  - executor_ms
- token usage
- retry_count
- fallback_rate
- tool_failure_rate

### Key Insight (from eval)

- Tool Accuracy: 100%
- LLM Usage: 0%
- Execution dominates latency
- RAG = primary bottleneck

---

## 11. Caching Layers

### Response Cache
- query-level caching

### Plan Cache
- plan-level reuse

### Semantic Cache
- embedding similarity

### Inflight Registry
- deduplicates concurrent identical requests

Impact:
- reduces latency
- avoids duplicate execution

---

## 12. Resilience Layer

- Circuit Breaker (LLM + RAG)
- Retry with backoff
- Rate limiting
- Fallback execution

Failure:
- system_failure

---

## 13. Memory Layer

- session-scoped history
- used in planning context

---

## 14. Key Design Principles

From README  [oai_citation:1‡readme.md](sediment://file_0000000099a07207b100a1ea9ded8684):

- LLM cannot control execution
- Orchestrator is source of truth
- Tools are deterministic
- RAG is bounded
- System works without cloud

---

## 15. Updated Execution Reality (Post-Eval)

| Component     | Usage |
|--------------|------|
| Fast Path     | ~90% |
| LLM           | ~0% |
| Tools         | ~90% |
| RAG           | ~10% |

Conclusion:
System behaves as deterministic engine, not agent system.

---

## 16. Failure Mapping

| Layer        | Failure Type        |
|-------------|---------------------|
| Classifier   | planning_failure    |
| Planner      | planning_failure    |
| RAG          | retrieval_failure   |
| Tools        | tool_failure        |
| Infra        | system_failure      |
| Performance  | latency_failure     |

---

## 17. Tradeoffs

| Decision | Choice | Tradeoff |
|--------|-------|---------|
| Execution | Deterministic | Less flexible |
| Planning | Hybrid | Added complexity |
| RAG | Bounded | Limited coverage |
| Fast Path | Aggressive | Requires strict rules |

---

## 18. End-to-End Summary

- Deterministic core with LLM assist (not control)
- Fast-path eliminates LLM for structured queries
- Execution is fully observable
- RAG is isolated and measurable bottleneck
- System optimized for reliability over autonomy