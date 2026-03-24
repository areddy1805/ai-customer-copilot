import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()

        timestamps = self.requests[key]

        # remove old requests
        self.requests[key] = [t for t in timestamps if now - t < self.window]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True
