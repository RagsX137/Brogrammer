import json
import functools
from typing import TypeVar

from pydantic import ValidationError

T = TypeVar("T")


def with_retries(retries: int = 3, on: tuple = (json.JSONDecodeError, ValidationError, ConnectionError, TimeoutError, OSError)):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except on as e:
                    last_error = e
                    if attempt == retries - 1:
                        raise RuntimeError(f"{func.__name__} failed after {retries} retries: {e}") from e
            raise RuntimeError(f"{func.__name__} failed after {retries} retries: {last_error}")
        return wrapper
    return decorator
