EVAL_QUERIES = [
    # ---------------- BASIC FLOWS ----------------
    {
        "query": "Where is my order ORD1?",
        "expected_intent": "order_status",
        "expected_contains": "ORD1",
        "expected_route": "tool",
    },
    {
        "query": "I want refund for ORD2",
        "expected_intent": "refund_request",
        "expected_contains": "ORD2",
        "expected_route": "tool",
    },
    {
        "query": "Create ticket for ORD3 issue",
        "expected_intent": "create_ticket",
        "expected_contains": "Ticket",
        "expected_route": "tool",
    },
    {
        "query": "What is refund policy?",
        "expected_intent": "refund_policy",
        "expected_contains": "refund",
        "expected_route": "rag",
    },
    # ---------------- MULTI-INTENT ----------------
    {
        "query": "Track ORD1 and refund ORD2",
        "expected_intent": "refund_request",
        "expected_contains": [
            "Refund status for order ORD1",
            "Refund status for order ORD2",
        ],
    },
    {
        "query": "Refund ORD2 and create ticket",
        "expected_intent": "refund_request",
        "expected_contains": "ORD2",
        "expected_route": "tool",
    },
    # ---------------- MISSING ENTITY ----------------
    {
        "query": "Where is my order?",
        "expected_intent": "order_status",
        "expected_contains": "order",
        "expected_route": "tool",
    },
    {
        "query": "Refund my order",
        "expected_intent": "refund_request",
        "expected_contains": "refund",
        "expected_route": "tool",
    },
    # ---------------- INVALID ENTITY ----------------
    {
        "query": "Where is my order ORD999?",
        "expected_intent": "order_status",
        "expected_contains": "ORD999",
        "expected_route": "tool",
    },
    # ---------------- ADVERSARIAL / NATURAL LANGUAGE ----------------
    {
        "query": "I didn’t get my package for ORD1",
        "expected_intent": "delivery_issue",
        "expected_contains": "ORD1",
        "expected_route": "tool",
    },
    {
        "query": "I want my money back for ORD2 now",
        "expected_intent": "refund_request",
        "expected_contains": "ORD2",
        "expected_route": "tool",
    },
    # ---------------- NOISE / AMBIGUITY ----------------
    {
        "query": "Order?",
        "expected_intent": "order_status",
        "expected_contains": "order",
        "expected_route": "tool",
    },
    {
        "query": "Refund?",
        "expected_intent": "refund_request",
        "expected_contains": "refund",
        "expected_route": "tool",
    },
    {
        "query": "Help",
        "expected_intent": None,  # allow flexibility
        "expected_contains": "",
    },
]
