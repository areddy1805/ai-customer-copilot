from typing import List, Dict
from app.memory.redis_client import RedisClient


class MemoryService:
    def __init__(self):
        self.redis = RedisClient()
        self.max_messages = 10

    def _get_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_messages(self, session_id: str) -> List[Dict]:
        key = self._get_key(session_id)
        messages = self.redis.get(key)

        if messages is None:
            return []

        return messages

    def add_message(self, session_id: str, role: str, content: str):
        key = self._get_key(session_id)

        messages = self.get_messages(session_id)

        messages.append({"role": role, "content": self._sanitize(content)})

        messages = messages[-self.max_messages :]

        for m in messages:
            m["content"] = self._sanitize(m.get("content"))

        self.redis.set(key, messages, ttl=3600)

    def clear(self, session_id: str):
        key = self._get_key(session_id)
        self.redis.delete(key)

    def get_history(self, session_id: str):
        return self.get_messages(session_id)

    def _sanitize(self, value):
        if isinstance(value, str):
            return value
        if hasattr(value, "data"):
            data = getattr(value, "data", None)
            if isinstance(data, dict) and "response" in data:
                return data["response"]
            return str(data)
        return str(value)
