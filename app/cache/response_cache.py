import redis
import json


class ResponseCache:
    def __init__(self):
        self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def _key(self, query: str) -> str:
        return f"response:{query.strip().lower()}"

    def get(self, query: str):
        data = self.client.get(self._key(query))
        return json.loads(data) if data else None

    def set(self, query: str, response: str, ttl: int = 300):
        self.client.setex(self._key(query), ttl, json.dumps(response))
