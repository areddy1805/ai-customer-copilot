import redis
import json
from typing import Any, Optional
from app.core.config import settings


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store value in Redis with optional TTL (seconds)
        """
        serialized = json.dumps(value)

        if ttl:
            self.client.setex(key, ttl, serialized)
        else:
            self.client.set(key, serialized)  # ← CRITICAL FIX

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from Redis
        """
        data = self.client.get(key)

        if data is None:
            return None

        return json.loads(data)

    def delete(self, key: str):
        """
        Delete key from Redis
        """
        self.client.delete(key)
