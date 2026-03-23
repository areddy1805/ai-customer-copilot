from app.orchestrator.orchestrator import Orchestrator

orch = Orchestrator()

session_id = "rag_test"

queries = [
    "Where is my order ORD2?",
    "I want refund for ORD3",
    "My delivery is delayed for ORD4",
    "When will i get my refund money",
]

for q in queries:
    state = orch.run(q, session_id=session_id)

    print("\nQUERY:", q)
    print("INTENT:", state.intent)
    print("ROUTE:", state.metadata.get("route"))
    print("RESPONSE:", state.final_response)
