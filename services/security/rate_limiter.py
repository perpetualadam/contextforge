"""
Distributed Rate Limiting Module.

Provides Redis-based distributed rate limiting with sliding window algorithm.

Copyright (c) 2025 ContextForge
"""

import os
import time
import logging
from typing import Optional, Dict, List
from collections import defaultdict

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
USE_REDIS_RATE_LIMIT = os.getenv("USE_REDIS_RATE_LIMIT", "true").lower() in ("true", "1", "yes")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class InMemoryRateLimiter:
    """In-memory rate limiter (for development/single instance)."""
    
    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed using sliding window."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]
        
        # Check if under limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Count requests in current window
        current_requests = sum(
            1 for req_time in self.requests.get(client_id, [])
            if req_time > window_start
        )
        
        return max(0, self.max_requests - current_requests)
    
    def get_reset_time(self, client_id: str) -> int:
        """Get timestamp when rate limit resets."""
        requests = self.requests.get(client_id, [])
        if not requests:
            return int(time.time())
        
        oldest_request = min(requests)
        return int(oldest_request + self.window_seconds)


class RedisRateLimiter:
    """Redis-based distributed rate limiter."""
    
    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            self.redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis rate limiter initialized")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory rate limiter.")
            self.redis_client = None
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed using Redis sliding window."""
        if not self.redis_client:
            # Fallback to in-memory
            return InMemoryRateLimiter(self.max_requests, self.window_seconds).is_allowed(client_id)
        
        try:
            key = f"rate_limit:{client_id}"
            now = time.time()
            window_start = now - self.window_seconds
            
            # Use Redis sorted set for sliding window
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiration
            pipe.expire(key, self.window_seconds + 1)
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count < self.max_requests
        
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open (allow request) on Redis errors
            return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client."""
        if not self.redis_client:
            return InMemoryRateLimiter(self.max_requests, self.window_seconds).get_remaining(client_id)
        
        try:
            key = f"rate_limit:{client_id}"
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old entries and count
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = pipe.execute()
            
            current_count = results[1]
            return max(0, self.max_requests - current_count)
        
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return self.max_requests

    def get_reset_time(self, client_id: str) -> int:
        """Get timestamp when rate limit resets."""
        if not self.redis_client:
            return InMemoryRateLimiter(self.max_requests, self.window_seconds).get_reset_time(client_id)

        try:
            key = f"rate_limit:{client_id}"

            # Get oldest request in window
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                return int(oldest_time + self.window_seconds)

            return int(time.time())

        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            return int(time.time())


def get_rate_limiter() -> RedisRateLimiter:
    """Get rate limiter instance (Redis or in-memory)."""
    if USE_REDIS_RATE_LIMIT:
        return RedisRateLimiter()
    else:
        return InMemoryRateLimiter()


def get_client_id(request: Request) -> str:
    """Extract client identifier from request."""
    # Try to get user ID from JWT token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from .jwt_auth import get_jwt_manager
            manager = get_jwt_manager()
            token = auth_header.split(" ")[1]
            token_data = manager.decode_token(token)
            return f"user:{token_data.get('user_id', 'unknown')}"
        except Exception:
            pass

    # Fallback to IP address
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get first IP in chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    return f"ip:{client_ip}"


async def check_rate_limit(request: Request) -> None:
    """
    FastAPI dependency to check rate limit.

    Raises HTTPException if rate limit exceeded.
    """
    if not RATE_LIMIT_ENABLED:
        return

    rate_limiter = get_rate_limiter()
    client_id = get_client_id(request)

    if not rate_limiter.is_allowed(client_id):
        remaining = rate_limiter.get_remaining(client_id)
        reset_time = rate_limiter.get_reset_time(client_id)

        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW} seconds.",
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(RATE_LIMIT_WINDOW)
            }
        )

