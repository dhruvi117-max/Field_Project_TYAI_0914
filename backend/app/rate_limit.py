"""Deliberately small in-memory limit for costly audit uploads.

For a multi-instance deployment this must be replaced with Redis/API-gateway limits.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from .core import get_settings

_WINDOW_SECONDS = 60.0
_REQUESTS: defaultdict[str, deque[float]] = defaultdict(deque)


async def limit_audit_requests(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    entries = _REQUESTS[client]
    while entries and now - entries[0] >= _WINDOW_SECONDS:
        entries.popleft()
    if len(entries) >= get_settings().max_audits_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many audit uploads. Please wait one minute before trying again.",
        )
    entries.append(now)
