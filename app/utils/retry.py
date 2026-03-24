import time


def retry(fn, retries=2, delay=0.5):
    last_exception = None

    for _ in range(retries):
        try:
            return fn()
        except Exception as e:
            last_exception = e
            time.sleep(delay)

    raise last_exception
