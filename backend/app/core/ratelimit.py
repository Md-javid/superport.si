"""Tiny in-memory rate limiter for auth endpoints (single process). Use Redis when you scale out."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque] = defaultdict(deque)


def check(key: str, limit: int, window_seconds: int = 60) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    q.append(now)


def reset() -> None:
    _hits.clear()
