# AI Customer Support Copilot

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![LLM](https://img.shields.io/badge/LLM-Ollama-orange)
![UI](https://img.shields.io/badge/UI-Vanilla%20JS-black)
![Streaming](https://img.shields.io/badge/Streaming-SSE-blueviolet)
![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

Production-grade AI system for e-commerce customer support with **deterministic orchestration, async execution, pluggable LLMs, streaming UI, RAG grounding, and multi-intent reasoning**.

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
- Supports multi-intent queries deterministically
- Streams responses in real time

---

## Core Capabilities

### Deterministic Orchestration

- Planner-driven execution (no direct LLM control)
- Explicit step-by-step tool execution
- Zero hallucination for critical actions

### Async Execution Pipeline

- Fully async orchestrator, RAG, and LLM layers
- Parallel tool execution for multi-intent queries
- Non-blocking streaming responses

### Pluggable LLM Layer

- Switchable providers (Azure OpenAI / Ollama)
- Provider abstraction via factory pattern
- Task-based model selection

### Streaming (End-to-End)

- SSE-based streaming API
- Real token streaming for RAG (LLM-driven)
- Simulated streaming for tool responses (consistent UX)

### Multi-Intent Handling

- Query decomposition (`AND`, `THEN`)
- Parallel execution via async gather
- Deterministic aggregation of results

### Tool Execution Layer

- Order status retrieval
- Refund processing with business rules
- Support ticket creation

### Memory System

- Session-based conversation tracking
- Context-aware execution

### RAG Integration

- Policy grounding (refunds, delivery rules)
- Strict grounding enforcement (no hallucinated policies)

### Guard & Safety Layer

- Prompt injection protection
- Input validation
- Controlled escalation

---

## Architecture

```mermaid
flowchart TD

A[User Query] --> B[API Layer - FastAPI]

B --> C[Orchestrator]

C --> D[Policy Guard]
C --> E[Intent Classifier]
C --> F[Memory Layer]

F --> F1[In-Memory Store]
F --> F2[Redis - optional]

C --> G[Decomposer]

G --> H[Planner]

H --> I[Executor]

I --> J[Order Tool]
I --> K[Refund Tool]
I --> L[Ticket Tool]

J --> M[Tool Results]
K --> M
L --> M

C --> N[RAG Service]

N --> N1[Retriever]
N1 --> N2[Vector DB (Chroma / FAISS)]
N --> N3[LLM Service]

C --> O[LLM Service]

O --> O1[Provider Factory]
O1 --> O2[Azure OpenAI]
O1 --> O3[Ollama]

M --> P[Response Builder]
N --> P

P --> Q[Streaming Layer (SSE)]

Q --> R[Client UI]

C --> S[Cache Layer]
S --> S1[Response Cache]
S --> S2[Semantic Cache]
S --> S3[In-flight Dedup]

C --> T[Security Layer]
T --> T1[Rate Limiter]
T --> T2[Concurrency Limiter]
T --> T3[Circuit Breaker]

C --> U[Observability]
U --> U1[Metrics]
U --> U2[Structured Logs]
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

## Evaluation System

Custom evaluation framework validates:

- Intent classification
- Response correctness
- Route selection (tool vs rag)
- Multi-step plan generation

Run:

`````markdown
````bash
python -m app.eval.eval_runner


---

## Running Locally

1. Setup Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


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

Tech Stack

Backend
	•	FastAPI
	•	Python

LLM
	•	Azure OpenAI
	•	Ollama (phi3, mistral, llama3, qwen)

Retrieval (RAG)
	•	Chroma / FAISS

Memory & State
	•	In-memory session store (extensible to Redis)

Frontend
	•	Vanilla JavaScript
	•	HTML / CSS
	•	Server-Sent Events (SSE) for streaming

Infrastructure (Optional)
	•	Docker
	•	Redis (for scaling memory/queues)

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


---

Future Improvements
	•	True streaming tool execution (event-driven tools)
	•	WebSockets (replace SSE)
	•	Distributed execution (Celery / queues)
	•	Persistent memory (Redis / DB)
	•	pgvector for production RAG
	•	Observability (tracing + dashboards)
	•	Auth + multi-user sessions
	•	UI improvements (history, sessions)

---

License

MIT License
````
`````

```

```
