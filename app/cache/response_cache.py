import redis
import json


class ResponseCache:
    def __init__(self):
        self.client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def set(self, key: str, value, ttl: int = 300):
        self.client.setex(key, ttl, json.dumps(value))

    def get(self, key: str):
        data = self.client.get(key)
        return json.loads(data) if data else None
