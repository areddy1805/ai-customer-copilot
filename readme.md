# AI Customer Support Copilot

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Ollama](https://img.shields.io/badge/LLM-Ollama-orange)
![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A production-grade, stateful AI system for e-commerce customer support with deterministic orchestration, tool execution, memory, and RAG grounding.

---

## Overview

This system is not a chatbot.

It is a **controlled AI system** that:

- Executes real actions (order tracking, refunds, tickets)
- Uses structured planning instead of raw LLM replies
- Maintains conversation memory
- Grounds responses using knowledge base (RAG)
- Supports multi-intent queries deterministically

---

## Core Capabilities

### Deterministic Orchestration

- Planner-driven execution (no direct LLM control)
- Explicit step-by-step tool execution
- Zero hallucination for critical actions

### Multi-Intent Handling

- Query decomposition (`AND`, `THEN`)
- Sequential plan execution
- Aggregated responses

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

---

## Architecture

User Query
↓
Guard Layer (validation)
↓
Intent Classifier (rule-first)
↓
Decomposer (multi-intent split)
↓
Planner (deterministic steps)
↓
Executor (tool chaining)
↓
Response Builder
↓
Memory + Cache + Metrics

---

## Project Structure

app/
├── api/ # FastAPI endpoints
├── orchestrator/ # Core brain (planner, executor, routing)
├── tools/ # Deterministic business logic
├── memory/ # Session memory (Redis/local)
├── rag/ # Knowledge retrieval system
├── guard/ # Safety + validation
├── eval/ # Evaluation framework
├── cache/ # Response + semantic cache
├── security/ # Rate limiting, circuit breaker
├── observability/ # Metrics + logging

data/
├── mock_db/ # Orders, refunds, tickets
├── knowledge_base/ # Policy documents

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


⸻

Running Locally

1. Setup Environment

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


⸻

2. Start Services

docker-compose up -d


⸻

3. Run API

uvicorn app.main:app --reload


⸻

4. Test via API

POST /chat
{
  "query": "Track ORD1 and refund ORD2"
}


⸻

Tech Stack
	•	FastAPI
	•	Ollama (phi3, mistral, llama, qwen)
	•	Redis (memory + queues)
	•	FAISS / Chroma (RAG)
	•	Python (core orchestration)

⸻

What Makes This Different

Feature	Chatbot	This System
Tool execution	❌	✅
Deterministic flow	❌	✅
Multi-intent support	❌	✅
Memory	Limited	Structured
RAG grounding	Partial	Integrated
Production readiness	Low	High


⸻

Future Improvements
	•	Replace FAISS with pgvector
	•	Add async execution for tools
	•	Introduce human-in-loop dashboard
	•	Streaming responses (SSE/WebSockets)
	•	Advanced observability dashboards

⸻

License

MIT License
```
