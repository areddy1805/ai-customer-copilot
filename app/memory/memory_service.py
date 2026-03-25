from typing import List, Dict
from app.memory.redis_client import RedisClient


class MemoryService:
    def __init__(self):
        self.redis = RedisClient()
        self.max_messages = 10

    def _get_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_messages(self, session_id: str) -> List[Dict]:
        """
        Retrieve conversation history
        """
        key = self._get_key(session_id)
        messages = self.redis.get(key)

        if messages is None:
            return []

        return messages

    def add_message(self, session_id: str, role: str, content: str):
        """
        Add a new message to memory
        """
        key = self._get_key(session_id)

        messages = self.get_messages(session_id)

        messages.append({"role": role, "content": content})

        messages = messages[-self.max_messages :]
        self.redis.set(key, messages, ttl=3600)

    def clear(self, session_id: str):
        """
        Clear session memory
        """
        key = self._get_key(session_id)
        self.redis.delete(key)

    def get_history(self, session_id: str):
        return self.get_messages(session_id)
