import json
import time
import redis


class EscalationService:
    def __init__(self, host="localhost", port=6379, db=0):
        self.client = redis.Redis(host=host, port=port, db=db)

        self.queue_name = "support:escalation_queue"

    def push(self, session_id: str, user_query: str, intent: str, reason: str):
        """
        Push escalation event to Redis queue
        """
        payload = {
            "session_id": session_id,
            "user_query": user_query,
            "intent": intent,
            "reason": reason,
            "timestamp": int(time.time()),
        }

        self.client.rpush(self.queue_name, json.dumps(payload))

    def pop(self):
        """
        Pop next escalation (for agent side)
        """

        data = self.client.lpop(self.queue_name)

        if data:
            return json.loads(data)
        return None
