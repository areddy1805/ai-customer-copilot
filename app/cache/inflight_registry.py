import threading


class InFlightRegistry:
    def __init__(self):
        self.lock = threading.Lock()
        self.inflight = {}

    def get(self, key):
        with self.lock:
            return self.inflight.get(key)

    def set(self, key, value):
        with self.lock:
            self.inflight[key] = value

    def delete(self, key):
        with self.lock:
            if key in self.inflight:
                del self.inflight[key]
