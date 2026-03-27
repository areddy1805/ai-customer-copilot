import json
from datetime import datetime


class Logger:
    def log_request(
        self,
        session_id: str,
        user_query: str,
        intent: str,
        route: str,
        plans: list,
        tools_used: list,
        latency_ms: int,
        status: str,
        error: str = None,
    ):
        log = {
            "event": "request_completed",
            "session_id": session_id,
            "query": user_query,
            "intent": intent,
            "route": route,
            "plans": plans or [],
            "tools_used": tools_used or [],
            "latency_ms": latency_ms,
            "status": status,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(json.dumps(log))
