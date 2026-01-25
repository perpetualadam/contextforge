"""
Security Middleware for FastAPI.

Integrates JWT auth, CSRF protection, rate limiting, audit logging, and security headers.

Copyright (c) 2025 ContextForge
"""

import os
import time
import logging
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .audit_logger import get_audit_logger, AuditEventType
from .csrf_protection import get_csrf_protection

logger = logging.getLogger(__name__)

# Security headers configuration
ENABLE_SECURITY_HEADERS = os.getenv("ENABLE_SECURITY_HEADERS", "true").lower() in ("true", "1", "yes")
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "true").lower() in ("true", "1", "yes")
HSTS_MAX_AGE = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year
CSP_POLICY = os.getenv(
    "CSP_POLICY",
    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'"
)

# Request size limits
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", str(10 * 1024 * 1024)))  # 10 MB default


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        if not ENABLE_SECURITY_HEADERS:
            return response
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = CSP_POLICY
        
        # HTTP Strict Transport Security (HSTS)
        if ENABLE_HSTS:
            response.headers["Strict-Transport-Security"] = f"max-age={HSTS_MAX_AGE}; includeSubDomains; preload"
        
        # X-Frame-Options (prevent clickjacking)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        
        # X-Content-Type-Options (prevent MIME sniffing)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection (legacy XSS protection)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Remove server header
        response.headers.pop("Server", None)
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request size limits."""
    
    def __init__(self, app: ASGIApp, max_size: int = MAX_REQUEST_SIZE):
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request body too large. Maximum size: {self.max_size} bytes"
                }
            )
        
        return await call_next(request)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests for audit purposes."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Extract client info
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        user_agent = request.headers.get("User-Agent")
        
        # Extract user info from JWT (if present)
        user_id = None
        username = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from .jwt_auth import get_jwt_manager
                manager = get_jwt_manager()
                token = auth_header.split(" ")[1]
                token_data = manager.decode_token(token)
                user_id = token_data.get("user_id")
                username = token_data.get("username")
            except Exception:
                pass
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Request failed: {e}")
            status_code = 500
            raise
        finally:
            # Log request
            duration_ms = (time.time() - start_time) * 1000
            
            audit_logger = get_audit_logger()
            audit_logger.log_api_request(
                user_id=user_id,
                username=username,
                client_ip=client_ip,
                method=request.method,
                path=str(request.url.path),
                status_code=status_code,
                duration_ms=duration_ms,
                user_agent=user_agent
            )
        
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce CSRF protection on state-changing requests."""
    
    def __init__(self, app: ASGIApp, exempt_paths: Optional[list] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/login",
            "/auth/register"
        ]
        self.csrf_protection = get_csrf_protection()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF check for safe methods and exempt paths
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)
        
        # Verify CSRF token
        try:
            self.csrf_protection.verify_csrf_token(request)
        except Exception as e:
            audit_logger = get_audit_logger()
            audit_logger.log_security_event(
                event_type=AuditEventType.CSRF_VIOLATION,
                user_id=None,
                username=None,
                client_ip=request.client.host if request.client else "unknown",
                details={"path": str(request.url.path), "error": str(e)},
                severity="warning"
            )
            return JSONResponse(
                status_code=403,
                content={"detail": str(e)}
            )
        
        return await call_next(request)

