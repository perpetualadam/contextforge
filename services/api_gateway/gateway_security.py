"""
Shared API gateway security: rate limiting, optional API keys, client identity.

Used by app.py and route modules (e.g. github_server_routes) to avoid duplicate logic and
ensure all sensitive routes share the same gates.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Optional bearer auth (API key when API_KEY_ENABLED)
security = HTTPBearer(auto_error=False)

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

API_KEY_ENABLED = os.getenv("API_KEY_ENABLED", "false").lower() == "true"
_raw_keys = os.getenv("API_KEYS", "") or ""
API_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}


class RateLimiter:
    """Simple in-memory rate limiter (per gateway process)."""

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id] if req_time > window_start
        ]
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        current_requests = len(
            [req_time for req_time in self.requests[client_id] if req_time > window_start]
        )
        return max(0, self.max_requests - current_requests)


rate_limiter = RateLimiter()


def apply_rate_limit_config(config) -> None:
    """
    After unified config is loaded, override rate limit values and reset the limiter.
    Safe to call with config=None (re-inits from current env-based module globals).
    """
    global RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, rate_limiter
    if config and hasattr(config, "security") and config.security is not None:
        RATE_LIMIT_REQUESTS = int(config.security.rate_limit_requests)
        RATE_LIMIT_WINDOW = int(config.security.rate_limit_window)
    rate_limiter = RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)


def get_client_id(request: Request) -> str:
    """Client id for rate limiting (first X-Forwarded-For hop when behind a proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Verify API key when API_KEY_ENABLED; otherwise no-op."""
    if not API_KEY_ENABLED:
        return None
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide Authorization: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provided_key = credentials.credentials
    if provided_key not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return provided_key


async def check_rate_limit(request: Request) -> None:
    if not RATE_LIMIT_ENABLED:
        return
    client_id = get_client_id(request)
    if not rate_limiter.is_allowed(client_id):
        remaining = rate_limiter.get_remaining(client_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW} seconds.",
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + RATE_LIMIT_WINDOW),
            },
        )
