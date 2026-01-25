# ContextForge Security Module

Comprehensive security features for ContextForge including JWT authentication, CSRF protection, rate limiting, and audit logging.

## Features

### 1. JWT Authentication (`jwt_auth.py`)
- **HS256** algorithm for token signing
- **Access tokens** (60 min expiry) and **refresh tokens** (7 day expiry)
- **Role-Based Access Control (RBAC)** with 4 roles:
  - `ADMIN` - Full system access
  - `USER` - Standard user access
  - `READONLY` - Read-only access
  - `SERVICE` - Service-to-service communication
- **Token revocation** using JTI blacklist
- **Password hashing** with Argon2id (primary) and bcrypt (fallback)

### 2. CSRF Protection (`csrf_protection.py`)
- **HMAC-SHA256** token signatures
- **Double-submit cookie pattern**
- **24-hour token expiration**
- Automatic validation on POST/PUT/DELETE requests

### 3. Distributed Rate Limiting (`rate_limiter.py`)
- **Redis-based** distributed rate limiting
- **Sliding window** algorithm
- **100 requests per 60 seconds** (configurable)
- **Fallback to in-memory** for single instances
- Per-client IP tracking with X-Forwarded-For support

### 4. Audit Logging (`audit_logger.py`)
- **15+ event types** for comprehensive tracking
- **Structured JSON logging**
- Tracks user ID, IP address, timestamp, and event details
- Events include:
  - Authentication (LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT)
  - API requests
  - Command execution
  - Tool calls
  - Security violations (RATE_LIMIT_EXCEEDED, CSRF_VIOLATION)

### 5. Security Middleware (`middleware.py`)
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **Request Size Limits**: 10 MB default maximum
- **Audit Logging**: Automatic logging of all API requests
- **CSRF Enforcement**: Automatic CSRF validation

## Installation

```bash
pip install -r requirements.txt
```

Required dependencies:
- `pyjwt>=2.8.0`
- `passlib[argon2]>=1.7.4`
- `argon2-cffi>=23.1.0`
- `bcrypt>=4.1.2`
- `redis>=5.0.0`

## Quick Start

### 1. Generate Secrets

```bash
# Linux/Mac
./scripts/setup_security.sh

# Windows
.\scripts\setup_security.ps1
```

### 2. Configure Environment

```bash
# JWT Configuration
JWT_SECRET_KEY=<from /run/secrets/jwt_secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# CSRF Configuration
CSRF_SECRET_KEY=<from /run/secrets/csrf_secret>
CSRF_TOKEN_EXPIRE_HOURS=24

# Rate Limiting
RATE_LIMIT_ENABLED=true
USE_REDIS_RATE_LIMIT=true
REDIS_URL=redis://:password@redis:6379/0
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Security Headers
ENABLE_SECURITY_HEADERS=true
ENABLE_HSTS=true
HSTS_MAX_AGE=31536000

# Request Limits
MAX_REQUEST_SIZE=10485760  # 10 MB
```

### 3. Integrate with FastAPI

```python
from fastapi import FastAPI, Depends
from services.security import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    AuditLoggingMiddleware,
    CSRFMiddleware,
    get_current_user,
    require_admin,
    User
)

app = FastAPI()

# Add security middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(CSRFMiddleware, exempt_paths=["/health", "/auth/login"])

# Protected endpoint
@app.get("/protected")
async def protected_endpoint(user: User = Depends(get_current_user)):
    return {"message": f"Hello {user.username}"}

# Admin-only endpoint
@app.post("/admin")
async def admin_endpoint(user: User = Depends(require_admin)):
    return {"message": "Admin access granted"}
```

## Usage Examples

### Authentication

```python
from services.security import get_jwt_manager, User, UserRole

jwt_manager = get_jwt_manager()

# Create user
user = User(
    user_id="user_001",
    username="john_doe",
    email="john@example.com",
    roles=[UserRole.USER]
)

# Generate tokens
token_pair = jwt_manager.create_token_pair(user)
print(f"Access Token: {token_pair.access_token}")
print(f"Refresh Token: {token_pair.refresh_token}")

# Verify token
token_data = jwt_manager.decode_token(token_pair.access_token)
print(f"User ID: {token_data['user_id']}")

# Hash password
password_hash = jwt_manager.hash_password("secure_password")

# Verify password
is_valid = jwt_manager.verify_password("secure_password", password_hash)
```

### CSRF Protection

```python
from fastapi import Request, Response
from services.security import get_csrf_protection

csrf_protection = get_csrf_protection()

# Generate token
csrf_token = csrf_protection.generate_token(session_id="session_123")

# Set in cookie
csrf_protection.set_csrf_cookie(response, csrf_token)

# Verify token (in middleware or endpoint)
csrf_protection.verify_csrf_token(request, session_id="session_123")
```

### Rate Limiting

```python
from services.security import get_rate_limiter

rate_limiter = get_rate_limiter()

# Check if request is allowed
client_id = "192.168.1.1"
if rate_limiter.is_allowed(client_id):
    # Process request
    pass
else:
    # Return 429 Too Many Requests
    raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### Audit Logging

```python
from services.security import get_audit_logger, AuditEventType

audit_logger = get_audit_logger()

# Log API request
audit_logger.log_api_request(
    user_id="user_001",
    username="john_doe",
    client_ip="192.168.1.1",
    method="POST",
    path="/api/ingest",
    status_code=200,
    duration_ms=150.5,
    user_agent="Mozilla/5.0..."
)

# Log command execution
audit_logger.log_command_execution(
    user_id="user_001",
    username="john_doe",
    command="git status",
    working_dir="/workspace",
    exit_code=0,
    blocked=False
)

# Log security event
audit_logger.log_security_event(
    event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
    user_id="user_001",
    username="john_doe",
    client_ip="192.168.1.1",
    details={"requests": 101, "window": 60},
    severity="warning"
)
```

## Architecture

```
services/security/
├── __init__.py           # Module exports
├── jwt_auth.py           # JWT authentication and RBAC
├── csrf_protection.py    # CSRF token generation and validation
├── rate_limiter.py       # Distributed rate limiting
├── audit_logger.py       # Comprehensive audit logging
├── middleware.py         # FastAPI security middleware
└── README.md            # This file
```

## Security Best Practices

1. **Rotate secrets regularly** (JWT secret every 90 days)
2. **Monitor audit logs** for suspicious activity
3. **Use HTTPS in production** (TLS 1.2+)
4. **Enable all security headers**
5. **Configure rate limiting** based on your traffic patterns
6. **Review access logs** monthly
7. **Keep dependencies updated**

## Testing

```bash
# Run security tests
pytest tests/security/

# Test authentication flow
python -m pytest tests/security/test_jwt_auth.py

# Test rate limiting
python -m pytest tests/security/test_rate_limiter.py
```

## Troubleshooting

### JWT Token Errors
- Verify `JWT_SECRET_KEY` is set correctly
- Check token expiration times
- Ensure clock synchronization across services

### CSRF Validation Failures
- Verify `X-CSRF-Token` header is sent
- Check cookie is set correctly
- Ensure session ID matches

### Rate Limiting Issues
- Verify Redis connection
- Check `REDIS_URL` configuration
- Review rate limit settings

### Audit Log Not Writing
- Check file permissions on log directory
- Verify `AUDIT_LOG_ENABLED=true`
- Review log level configuration

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

## License

Copyright (c) 2025 ContextForge. All rights reserved.

