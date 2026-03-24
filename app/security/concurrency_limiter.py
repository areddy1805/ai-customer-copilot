import threading


class ConcurrencyLimiter:
    def __init__(self, max_concurrent=5):
        self.semaphore = threading.Semaphore(max_concurrent)

    def acquire(self):
        return self.semaphore.acquire(blocking=False)

    def release(self):
        self.semaphore.release()
