"""Conservative per-process sliding-window request and output-token budgets."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class RequestBudget:
    def __init__(self, requests: int, output_tokens: int) -> None:
        self._requests = requests
        self._output_tokens = output_tokens
        self._events: defaultdict[str, deque[tuple[float, int]]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def reserve(self, tenant: str, output_tokens: int = 0) -> None:
        async with self._lock:
            now = time.monotonic()
            events = self._events[tenant]
            while events and events[0][0] <= now - 60:
                events.popleft()
            if (
                len(events) >= self._requests
                or sum(tokens for _, tokens in events) + output_tokens > self._output_tokens
            ):
                raise HTTPException(
                    429, detail="request budget exhausted", headers={"Retry-After": "60"}
                )
            events.append((now, output_tokens))
