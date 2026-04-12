import time


class SimpleCache:
    def __init__(self, ttl=60):
        self.store = {}
        self.ttl = ttl

    def _key(self, tool_name, inputs):
        return f"{tool_name}:{str(sorted(inputs.items()))}"

    def get(self, tool_name, inputs):
        key = self._key(tool_name, inputs)
        entry = self.store.get(key)

        if not entry:
            return None

        if time.time() - entry["time"] > self.ttl:
            del self.store[key]
            return None

        return entry["value"]

    def set(self, tool_name, inputs, value):
        key = self._key(tool_name, inputs)
        self.store[key] = {
            "value": value,
            "time": time.time(),
        }
