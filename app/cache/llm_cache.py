import json
import hashlib
import redis


class LLMCache:
    def __init__(self):
        self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def _key(self, payload: dict):
        raw = json.dumps(payload, sort_keys=True)
        return "llm:" + hashlib.sha256(raw.encode()).hexdigest()

    def get(self, payload: dict):
        data = self.client.get(self._key(payload))
        return json.loads(data) if data else None

    def set(self, payload: dict, response: dict, ttl=3600):
        self.client.setex(self._key(payload), ttl, json.dumps(response))
