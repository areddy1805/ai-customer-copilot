import json
import time
from datetime import datetime


class Logger:
    """
    Simple structured logger
    """

    def log(self, event: str, data: dict):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            **data,
        }

        print(json.dumps(log_entry))

    def log_request(
        self,
        session_id: str,
        user_query: str,
        intent: str,
        route: str,
        execution: str,
        latency_ms: int,
        status: str,
    ):
        self.log(
            event="request_complete",
            data={
                "session_id": session_id,
                "query": user_query,
                "intent": intent,
                "route": route,
                "execution": execution,
                "latency_ms": latency_ms,
                "status": status,
            },
        )

    def log_error(self, session_id: str, error: str):
        self.log(
            event="error",
            data={
                "session_id": session_id,
                "error": error,
            },
        )
