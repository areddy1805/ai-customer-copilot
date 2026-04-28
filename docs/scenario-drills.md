# Scenario Drills

---

## 1. Customer Support AI (Deterministic Copilot)

### Problem
Automate customer support queries:
- order status
- cancellations
- refunds
- policy questions

Constraints:
- high reliability
- no hallucinations
- low latency
- predictable behavior

---

### Architecture

User → Guard → Classifier → Orchestrator →
Fast Path OR (Decomposer → Planner) →
Execution (Tools / RAG) → Composer → Response → Metrics

Key components:
- IntentClassifier (rule-based)
- Fast-path (order_id + keywords)
- Planner + PlanValidator (fallback only)
- Executor (tools + rag)
- ResponseComposer
- Observability (metrics + trace)

---

### Core Design Choice

Deterministic over agentic

Reason:
- tools must be correct (refund/order cannot hallucinate)
- system must be auditable
- behavior must be reproducible

LLM is:
- assistive (fallback only)
- not authoritative

---

### Fast Path (Critical Optimization)

If:
- order_id present
- query contains order/refund/cancel

Then:
→ direct plan creation (no LLM)

Impact:
- near-zero latency
- 100% tool accuracy (structured queries)
- eliminates planning failure

Observed:
- LLM usage ~0%
- execution dominates latency

---

### Execution Flow

1. Extract order_id
2. Split multi-intent (rule-based)
3. Create Plan:
   - refund(order_id)
   - order(order_id)

4. Execute:
   - ordered (order → refund)
5. Compose response

---

### Failure Handling

- Planning failure:
  → fallback to rule-based or rag

- Tool failure:
  → return structured failure (no hallucination)

- System failure:
  → guard / rate limit / circuit breaker

- Retrieval failure:
  → isolated to rag only

- Latency failure:
  → mitigated via caching

---

### Tradeoffs

| Decision | Benefit | Cost |
|--------|--------|------|
| Deterministic flow | high reliability | less flexible |
| Fast-path rules | speed + accuracy | rule maintenance |
| Limited LLM use | no hallucination | reduced generality |
| Bounded agent loop | predictable | limited reasoning depth |

---

### Key Insight

System behaves as:
- execution engine, not agent

---

## 2. RAG System

### Problem
Answer knowledge-based queries:
- refund policy
- FAQs
- documentation queries

---

### Pipeline

Query → Embed → Retrieve → Generate → Response

Components:
- Embedder
- Vector store
- Retriever
- Generator (LLM or template)

---

### Flow in Your System

Intent = refund_policy → direct RAG bypass

Steps:
1. embed query
2. retrieve relevant chunks
3. generate response
4. return

Planner is skipped

---

### Bottleneck

Observed:
- ~2.8–3s latency
- executor dominates

Cause:
- retrieval + generation cost

---

### Failure Modes

- retrieval_failure:
  - irrelevant chunks
  - missing docs

Detection:
- keyword mismatch
- correct tool but wrong answer

---

### Optimizations

- better chunking
- metadata filtering
- re-ranking
- caching:
  - semantic cache
  - response cache

---

### Tradeoffs

| Decision | Benefit | Cost |
|--------|--------|------|
| RAG isolation | clean architecture | added latency |
| local embeddings | control | lower quality |
| no planner | simplicity | less reasoning |

---

### Key Insight

RAG is:
- only non-deterministic part
- primary latency source

---

## 3. Agent System (Contrast)

### What is an Agent System

LLM controls:
- tool selection
- execution order
- reasoning loop

Flow:

User → LLM → decides tool → executes → observes → repeats

---

### Characteristics

- dynamic planning
- iterative reasoning
- flexible workflows

---

### Problems

1. Hallucination
   - wrong tool selection
   - fabricated steps

2. Unbounded loops
   - retries without control

3. Non-determinism
   - same input → different output

4. Debug difficulty
   - no clear trace

---

### Example Failure

Query:
"Cancel and refund order"

Agent might:
- call refund before cancel
- call wrong tool
- loop multiple times

---

### Why Your System Avoids This

- fixed execution graph
- rule-based overrides
- bounded steps (MAX_AGENT_STEPS = 2)
- strict plan validation

---

### Tradeoffs vs Your System

| Aspect | Agent System | Your System |
|------|-------------|------------|
| Flexibility | high | medium |
| Reliability | low | high |
| Latency | unpredictable | stable |
| Debugging | hard | easy |
| Control | low | high |

---

### When Agents Make Sense

- open-ended tasks
- research workflows
- multi-step reasoning problems

Not suitable for:
- financial actions
- transactional systems
- customer operations

---

## Final Positioning

Your system:

- deterministic core
- LLM-assisted (not LLM-driven)
- tool-first architecture
- observable and measurable

"Built a deterministic AI system with optional LLM assistance, eliminating hallucination risk while maintaining high accuracy and traceability."