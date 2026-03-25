import threading


class InFlightRegistry:
    def __init__(self):
        self.store = {}
        self.lock = threading.Lock()

    def set_if_absent(self, key: str) -> bool:
        """
        Atomically set key if not present.
        Returns:
            True  -> key was absent, now reserved
            False -> key already exists
        """
        with self.lock:
            if key in self.store:
                return False
            self.store[key] = None
            return True

    def set(self, key: str, value):
        with self.lock:
            self.store[key] = value

    def get(self, key: str):
        with self.lock:
            return self.store.get(key)

    def delete(self, key: str):
        with self.lock:
            if key in self.store:
                del self.store[key]
