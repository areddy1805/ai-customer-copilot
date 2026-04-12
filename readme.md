# AI Customer Support Copilot (Hybrid Deterministic AI System)

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![LLM](https://img.shields.io/badge/LLM-Hybrid%20(Local%20%2B%20Azure)-orange)
![RAG](https://img.shields.io/badge/RAG-Azure%20AI%20Search%20%7C%20Local-blue)
![Streaming](https://img.shields.io/badge/Streaming-SSE-blueviolet)
![Orchestration](https://img.shields.io/badge/Execution-Deterministic-critical)
![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

Production-grade AI system with **deterministic orchestration, tool-first execution, hybrid LLM (Local ↔ Azure), RAG (Azure AI Search / local), memory, and extensible planning layer (agentic WIP)**.

---

## 🎥 Demo

[![Watch Demo](assets/ui.png)](https://files.catbox.moe/y608uh.mp4)

## ⬇️ Download: https://github.com/areddy1805/ai-customer-copilot/releases/download/v1.0/demo.mp4

## Screenshots

<table>
<tr>
<td><img src="assets/ui.png"></td>
<td><img src="assets/stream.png"></td>
</tr>
<tr>
<td><img src="assets/slot.png"></td>
<td><img src="assets/multi.png"></td>
</tr>
<tr>
<td colspan="2"><img src="assets/rag_tool.png"></td>
</tr>
</table>

## Overview

This is not a chatbot.

This is a **controlled AI execution system** where:

- Executes real actions (order tracking, refunds, tickets)
- Uses structured planning instead of raw LLM replies
- Maintains conversation memory
- Grounds responses using knowledge base (RAG)
- Supports structured multi-step execution (rule-based, agentic layer in progress)

## Architecture Principles

- LLM is stateless and does not control execution
- Orchestrator owns all decision-making and tool invocation
- RAG is assistive, not authoritative
- Azure services are pluggable, not required
- System supports hybrid execution (local ↔ cloud)

## Azure Integration

- Azure OpenAI (Responses API)
- Azure AI Search (vector + hybrid retrieval)
- Azure Embeddings
- Azure Key Vault (planned)
- Azure Blob Storage (planned)

---

## Branches

| Branch | Description |
|--------|------------|
| main | Production-ready system (Hybrid Azure + Resilience + Adapter-ready, agentic in progress) |
| release/v1-local | Deterministic local-only baseline (stable snapshot) |
| feature/azure-migration | Introduces Azure OpenAI, embeddings, AI Search |
| feature/agentic-framework | Adds deterministic agent planner + structured execution |
| feature/framework-adapters | LangChain + AutoGen compatibility layer (non-core) |

---

## Agentic Implementations (WIP)

| Mode | Description |
|------|------------|
| Core Agent (Custom) | Deterministic, production-grade planner-executor |
| LangChain Adapter | Framework-based agent (demo only) |
| AutoGen Adapter | Multi-agent simulation (experimental) |

---

## Security & Secrets

Secrets are not stored in code or config.

### Secret Management

- Azure Key Vault (primary)
- Env-based fallback (local development only)

- Rule-based query decomposition (`AND`, `THEN`)
- Sequential execution pipeline
- Agentic planning layer will replace this with dynamic plan generation

SECRET_PROVIDER=env | keyvault

Architecture:

Providers → SecretProvider → (Env OR Key Vault)

### Key Vault Integration

- Secrets fetched at runtime
- In-memory caching (no repeated network calls)
- No secrets in `.env` (production mode)

### Naming Constraint Handling

Azure Key Vault does not support underscores.

Internal mapping layer converts:

AZURE_OPENAI_API_KEY → azure-openai-api-key

## SYSTEM EVOLUTION

### BEFORE
- Local LLM (Ollama)
- Local embeddings
- Chroma vector DB

### NOW (HYBRID)
- Secrets → Azure Key Vault (secure, runtime retrieval)
- LLM → Azure (primary) + Local (automatic fallback)
- Resilience → Retry + Timeout + Circuit Breaker enforced
- Response Cache → request-level caching (Redis/in-memory)

---

## Core Capabilities

### Deterministic Orchestration
- Planner → Executor pipeline
- No direct LLM tool execution
- Guaranteed execution correctness

### Hybrid LLM Layer
- Azure OpenAI (primary)
- Ollama (automatic fallback)
- Retry + timeout enforced on Azure calls
- Circuit breaker prevents cascading failures

Behavior:

Azure success → used
Azure failure → automatic fallback to local

### Hybrid Embeddings
- Local: SentenceTransformers
- Azure: text-embedding-3-small
- Config-driven switching

### RAG (Controlled + Hybrid Retrieval)
- Retriever + strict grounding
- LLM cannot override retrieved facts
- Post-response enforcement
- Backend: Chroma OR Azure AI Search
- Azure enables hybrid retrieval (vector + keyword)

### Async + Streaming
- Fully async pipeline
- SSE streaming for responses
- Parallel execution for multi-intent

### Multi-Intent Execution
- Query decomposition
- Parallel tool execution
- Deterministic aggregation

### Tool Layer (Pure Functions)
- Order tracking
- Refund processing
- Ticket creation

### Memory Layer
- Session-scoped context
- Extendable to Redis

### Guardrails
- Input validation
- Prompt injection protection
- Execution safety

### Resilience Layer

- Retry with exponential backoff (Azure calls)
- Timeout enforcement (prevents hanging requests)
- Circuit breaker (failure isolation)
- Automatic fallback (Azure → Local)

Ensures system never fails due to external dependency.

## Hybrid Execution Control

System supports runtime switching:

- LLM Provider → Local | Azure
- Embeddings → Local | Azure
- RAG Backend → Local | Azure AI Search

All switches are configuration-driven. No code changes required.

## System Positioning

This system is designed as:

- A deterministic alternative to LLM-first agents
- A hybrid AI architecture (local + cloud)
- A production-ready foundation for enterprise copilots

Not:
- a prompt-based chatbot
- a framework-dependent agent

## Execution Transparency

- Every request produces an explicit execution path
- Plans can be logged, inspected, and replayed
- System behavior is debuggable at step level

## Resilience & Failure Handling

- Retry logic for tool execution
- Fallback between Azure and local providers
- Timeout and circuit breaker controls

---

## Architecture

```mermaid
flowchart TD

A[User] --> B[FastAPI]
B --> C[Orchestrator]

C --> D[Policy Guard]
C --> E[Intent Parser - Rule Based]
C --> F[Memory Context]
C --> G[Task Decomposer]
G --> H[Planner / Agent Planner]

C --> I[RAG Service]
I --> I4[Search Provider]
I4 --> I5[Chroma Local]
I4 --> I6[Azure AI Search Hybrid]

I --> R1[Retry and Timeout]
R1 --> R2[Circuit Breaker]

C --> J[LLM Service]
I --> J

J --> J1[Retry and Timeout]
J1 --> J2[Azure OpenAI Primary]
J2 -->|failure| J3[Local LLM Fallback]

J --> S[Secret Provider]
S --> S1[Env Local]
S --> S2[Azure Key Vault]
I --> S

C --> N[Memory]

C --> O[Streaming Layer]
O --> P[Client]

J --> Z[Response]
R2 --> J
```

---

Provider Abstraction (Core Design)

LLM

LLM_PROVIDER=local | azure

	•	Local → Ollama
	•	Azure → Responses API

---

Embeddings

EMBEDDING_PROVIDER=local | azure

	•	Local → SentenceTransformers
	•	Azure → text-embedding-3-small

---

Search Provider (RAG Backend)

SEARCH_PROVIDER=local | azure

• Local → Chroma (vector-only retrieval)
• Azure → Azure AI Search (hybrid: vector + keyword)

Key Behavior:
• Each provider maintains its own index
• Switching provider requires reindex
• No shared storage between providers

---

Key Insight (From Evaluation)

System behavior:

~90% → Tool execution
~10% → RAG usage

Implication:
	•	Orchestrator dominates correctness
	•	RAG quality matters only when invoked

---

Embedding Evaluation Result

Query	Local	Azure
didnt receive package	PASS	PASS+
item came broken	PASS	PASS+
shipping time	FAIL	PASS
cancel after ordering	PASS	PASS+

Conclusion
	•	Azure embeddings improve semantic retrieval
	•	Local embeddings rely on keyword overlap
	•	System now exposes real retrieval differences

---

## Project Structure

```

.
├── app/
│ ├── api/ # FastAPI endpoints (chat, health)
│ ├── orchestrator/ # Core brain (planning, execution, routing)
│ │ ├── orchestrator.py
│ │ ├── planner.py
│ │ ├── executor.py
│ │ ├── decomposer.py
│ │ ├── classifier.py
│ │ └── ...
│ ├── tools/ # Business logic (order, refund, ticket)
│ ├── rag/ # Retrieval system (embeddings, vector store)
│ ├── memory/ # Session memory (Redis/local)
│ ├── guard/ # Validation + safety layer
│ ├── cache/ # Response + semantic caching
│ ├── security/ # Rate limiting, circuit breaker, concurrency
│ ├── observability/ # Metrics + logging
│ ├── llm/ # provider abstraction (Azure / Ollama) /LLM client + prompt layer
│ ├── eval/ # Evaluation framework
│ ├── core/ # Config + logging setup
│ └── main.py # Entry point
│
├── client/ # UI (HTML/CSS/JS)
│ ├── index.html
│ └── app.js
|
├── data/
│ ├── mock_db/ # Mock business data (orders, refunds, tickets)
│ ├── knowledge_base/ # Policy documents for RAG
│ └── chroma/ # Vector store (auto-generated)
│
├── infra/
│ ├── Dockerfile
│ └── docker-compose.yml
|
├── assets/ # screenshots + demo video
│ ├── ui.png
│ ├── stream.png
│ ├── slot.png
│ ├── multi.png
│ ├── rag_tool.png
│ └── demo.mp4
│
├── scripts/ # Utility scripts
├── tests/ # Test cases
├── requirements.txt
└── README.md

```

---

## Key Design Decisions

### 1. No Direct LLM Control

LLM is not allowed to:

- call tools
- decide execution
- modify system state

All decisions are orchestrator-controlled.

---

### 2. Planner-Centric Execution

Planner defines execution path.
Router only assists.

---

### 3. Stateless Tools + Stateful Orchestrator

- Tools = pure functions
- Orchestrator = state + control

---

### 4. Async + Parallel by Default

- Multi-intent → parallel execution
- Streaming → non-blocking
- System remains responsive under load

---

### 5. Multi-Step Execution as First-Class Citizen

Every query is treated as:

Query → Tasks → Plans → Execution

### 5. Execution Guarantees

- Every tool call is explicitly planned and validated
- No implicit LLM-triggered actions
- All execution paths are traceable and reproducible

---

## Example Flows

### Single Intent

Where is my order ORD1?
→ Plan: [order]
→ Response: Order status + ETA

### Multi Intent

Track ORD1 and refund ORD2
→ Plans:
[order ORD1]
[order ORD2 → refund ORD2]

→ Response:
Order + Refund combined (deterministic order)

### RAG + Streaming

What is refund policy

→ Routed to RAG
→ LLM streams tokens
→ Grounded response enforced

→ Response:
Grounded response

---

---

Configuration

.env (control only — no secrets)

```text
LLM_PROVIDER=local | azure
EMBEDDING_PROVIDER=local | azure
SEARCH_PROVIDER=local | azure

SECRET_PROVIDER=env | keyvault
AZURE_KEY_VAULT_URL=https://<vault>.vault.azure.net/
```

Note:

- Azure secrets must NOT be stored in `.env`
- All secrets are fetched from Azure Key Vault in production mode

---

Runtime Visibility

Logs active providers at startup:

[CONFIG] LLM_PROVIDER=local
[CONFIG] EMBEDDING_PROVIDER=azure
[CONFIG] SEARCH_PROVIDER=azure


---

Running

1. Install

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


---

2. Reindex (CRITICAL)

python -m scripts.reindex

Must be run after:
	•	embedding switch
	•	knowledge base change
  • search provider switch (local ↔ azure)

---

3. Run API

uvicorn app.main:app --reload


---

4. Run UI

cd client
python -m http.server 3000


---

5. Test

curl "http://localhost:8000/api/chat?query=Track%20ORD1%20and%20refund%20ORD2"


---

Evaluation

System Eval

python -m app.eval.eval_runner

Validates:
	•	intent classification
	•	tool routing
	•	execution correctness

---

Retriever Eval

python -m scripts.test_retriever

Validates:
	•	embedding quality
	•	semantic retrieval
	•	chunk relevance

---

## Evaluation System

Custom evaluation framework validates:

- Intent classification
- Response correctness
- Route selection (tool vs rag)
- Multi-step plan generation

Run:

```bash
python -m app.eval.eval_runner
```

---

## Running Locally

1. Setup Environment

```text
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


---

2. Docker Setup

Start Full Stack

docker-compose -f infra/docker-compose.yml up --build

Services
	•	API → http://localhost:8000
	•	Redis → localhost:6379
	•	Postgres → localhost:5432
	•	Ollama → http://localhost:11434

---

Pull LLM Model

docker exec -it copilot-ollama ollama pull phi3


---

Stop

docker-compose -f infra/docker-compose.yml down


---

3. Run API (Without Docker)

uvicorn app.main:app --reload


---

4. Start UI

cd client
python -m http.server 3000

Open:

http://localhost:3000


---

5. Test via API

curl "http://localhost:8000/api/chat?query=Track%20ORD1%20and%20refund%20ORD2"


---

## Tech Stack

### Backend
- FastAPI
- Python

### LLM Providers
- Local (Ollama)
- Azure OpenAI (Responses API)

### Retrieval (RAG)
- Local (Chroma / FAISS)
- Azure AI Search (vector + hybrid)

### Embeddings
- Local models
- Azure Embeddings

### Memory
- In-memory (dev)
- Redis (optional)

### Frontend
- Vanilla JavaScript (SSE streaming)

### Infrastructure
- Docker
- Redis
- Azure (OpenAI, AI Search, Key Vault, Blob - planned)

---

## What Makes This Different

| Feature                | Chatbot | This System |
|------------------------|---------|-------------|
| Tool execution         | ❌      | ✅           |
| Deterministic flow     | ❌      | ✅           |
| Multi-intent support   | ❌      | ✅           |
| Async execution        | ❌      | ✅           |
| Streaming 		     | ❌      | ✅           |
| Memory                 | Limited | Structured  |
| RAG grounding          | Partial | Integrated  |
| Production readiness   | Low     | High        |
| Pluggable LLMs 	     | ❌      | ✅           |
| Observability          | Minimal | Integrated  |
| Safety / Guardrails    | Weak    | Enforced    |
| Production readiness   | Low	   | High        |


## Framework Independence

This system does not depend on agent frameworks (LangChain, AutoGen) for execution.

- Core logic is implemented as deterministic system components
- Frameworks are integrated only as optional adapters
- Execution control remains fully within the orchestrator

---

### Future Improvements

- Agentic planner (LLM-driven structured plan generation)
- DAG-based execution engine (dependency-aware execution)
- Tool-level caching and step reuse
- Persistent memory (Redis / DB-backed sessions)
- Distributed execution (queue-based workers)
- Advanced observability (tracing, dashboards)
- WebSocket streaming (replace SSE)
- Authentication + multi-tenant isolation

---

## Tradeoffs

MIT License

