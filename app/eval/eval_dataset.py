EVAL_QUERIES = [
    {
        "query": "Where is my order ORD1?",
        "expected_intent": "order_status",
        "expected_contains": "ORD1",
    },
    {
        "query": "I want refund for ORD2",
        "expected_intent": "refund_request",
        "expected_contains": "refund",
    },
    {
        "query": "Create ticket for ORD3 issue",
        "expected_intent": "create_ticket",
        "expected_contains": "ticket",
    },
    {
        "query": "What is refund policy?",
        "expected_route": "rag",
        "expected_contains": "refund",
    },
    {
        "query": "I want refund and track ORD1",
        "expected_multi": True,
    },
]
