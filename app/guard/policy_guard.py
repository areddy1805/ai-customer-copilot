import re
from typing import Dict


class PolicyGuard:
    """
    Deterministic safety and validation layer
    """

    def evaluate(self, query: str, intent: str) -> Dict:
        """
        Returns:
        {
            "allowed": bool,
            "action": "proceed" | "block" | "fallback",
            "reason": str
        }
        """

        query_lower = query.lower()

        # -------- 1. EMPTY INPUT --------
        if not query.strip():
            return {"allowed": False, "action": "block", "reason": "Empty query"}

        # -------- 2. LENGTH CHECK --------
        if len(query) > 500:
            return {"allowed": False, "action": "block", "reason": "Query too long"}

        # -------- 3. PROMPT INJECTION DETECTION --------
        injection_patterns = [
            "ignore previous instructions",
            "bypass rules",
            "act as admin",
            "give me all data",
            "override system",
        ]

        for pattern in injection_patterns:
            if pattern in query_lower:
                return {
                    "allowed": False,
                    "action": "block",
                    "reason": "Prompt injection detected",
                }

        # -------- 4. ORDER ID CHECK --------
        order_id = self._extract_order_id(query)

        if intent in ["order_status", "refund_request", "delivery_issue"]:
            if not order_id:
                return {
                    "allowed": True,
                    "action": "fallback",  # route to RAG
                    "reason": "Missing order_id",
                }

        return {"allowed": True, "action": "proceed", "reason": "Valid request"}

    def _extract_order_id(self, query: str):
        match = re.search(r"ORD\d+", query.upper())
        return match.group(0) if match else None
