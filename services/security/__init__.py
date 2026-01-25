"""
ContextForge Security Module.

Provides comprehensive security features:
- JWT authentication and authorization
- CSRF protection
- Distributed rate limiting
- Audit logging
- Security headers
- Request size limits

Copyright (c) 2025 ContextForge
"""

from .jwt_auth import (
    JWTAuthManager,
    User,
    UserRole,
    TokenPair,
    get_jwt_manager,
    get_current_user,
    require_admin,
    require_user
)

from .csrf_protection import (
    CSRFProtection,
    get_csrf_protection
)

from .rate_limiter import (
    RedisRateLimiter,
    InMemoryRateLimiter,
    get_rate_limiter,
    check_rate_limit,
    get_client_id
)

from .audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    get_audit_logger
)

from .middleware import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    AuditLoggingMiddleware,
    CSRFMiddleware
)

__all__ = [
    # JWT Auth
    "JWTAuthManager",
    "User",
    "UserRole",
    "TokenPair",
    "get_jwt_manager",
    "get_current_user",
    "require_admin",
    "require_user",
    
    # CSRF Protection
    "CSRFProtection",
    "get_csrf_protection",
    
    # Rate Limiting
    "RedisRateLimiter",
    "InMemoryRateLimiter",
    "get_rate_limiter",
    "check_rate_limit",
    "get_client_id",
    
    # Audit Logging
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "get_audit_logger",
    
    # Middleware
    "SecurityHeadersMiddleware",
    "RequestSizeLimitMiddleware",
    "AuditLoggingMiddleware",
    "CSRFMiddleware",
]

__version__ = "1.0.0"

