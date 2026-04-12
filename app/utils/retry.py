import asyncio


def retry(fn, retries=3, delay=0.5):

    async def wrapper(*args, **kwargs):
        last_exception = None

        for attempt in range(retries):
            try:
                return await fn(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt == retries - 1:
                    raise

                await asyncio.sleep(delay * (2**attempt))  # exponential backoff

        raise last_exception

    return wrapper
