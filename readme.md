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

This system is not a chatbot.

It is a **controlled AI system** that:

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

## Core Capabilities

### Deterministic Orchestration

- Planner-driven execution (no direct LLM control)
- Explicit step-by-step tool execution
- Zero hallucination for critical actions

### Multi-Intent Handling

- Rule-based query decomposition (`AND`, `THEN`)
- Sequential execution pipeline
- Agentic planning layer will replace this with dynamic plan generation

### Tool Execution Layer

- Order status retrieval
- Refund processing with business rules
- Support ticket creation

### Memory System

- Session-based conversation tracking
- Context-aware execution

### RAG Integration

- Policy grounding (refunds, delivery rules)
- Context injection without overload

### Guard & Safety Layer

- Prompt injection protection
- Input validation
- Controlled escalation

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

A[User Query] --> B[API Layer - FastAPI]

B --> C[Orchestrator]

C --> D[Policy Guard]
C --> E[Intent Parser (Rule-based)]
C --> F[Memory Context]

C --> G[Task Decomposer]

G --> H[Planner / Agent Planner]

H --> I[Executor]

I --> J[Order Tool]
I --> K[Refund Tool]
I --> L[Ticket Tool]

J --> M[Tool Results]
K --> M
L --> M

M --> N[RAG Service]

N --> O[Response Builder]

O --> P[Final Response]

P --> Q[Observability / Metrics]

G --> R[Cache Layer]
C --> R
```

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
│ ├── llm/ # LLM client + prompt layer
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

### 2. Planner > Router

Routing is simplified.
Planner defines execution path.

---

### 3. Stateless Tools + Stateful Orchestrator

- Tools are pure functions
- Orchestrator manages context and flow

---

### 4. Multi-Step Execution as First-Class Citizen

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
Order + Refund combined

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

```bash
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
| Memory                 | Limited | Structured  |
| RAG grounding          | Partial | Integrated  |
| Production readiness   | Low     | High        |


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

License

MIT License

