"""Small, explicit security control for the prototype; replace with OAuth before real deployment."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from .core import get_settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    configured_key = get_settings().api_key.strip()
    if configured_key and not (x_api_key and hmac.compare_digest(x_api_key, configured_key)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-API-Key")


async def require_auditor(x_user_role: str = Header(default="auditor")) -> None:
    if x_user_role.lower() not in {"auditor", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Auditor or admin role required")

