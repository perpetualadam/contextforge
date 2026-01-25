# Security Integration Guide

This guide provides ready-to-integrate code examples for all security features in ContextForge.

---

## Table of Contents
1. [Authentication Flow](#authentication-flow)
2. [API Gateway Integration](#api-gateway-integration)
3. [Web Frontend Integration](#web-frontend-integration)
4. [Terminal Executor Integration](#terminal-executor-integration)
5. [Testing Security Features](#testing-security-features)

---

## 1. Authentication Flow

### Login Example (Python)

```python
import requests

# Login to get JWT tokens
response = requests.post(
    "https://localhost:8443/auth/login",
    json={
        "username": "admin",
        "password": "your_password"
    },
    verify=False  # Only for self-signed certs in development
)

if response.status_code == 200:
    tokens = response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    
    # CSRF token is set in cookie automatically
    csrf_token = response.cookies.get("csrf_token")
    
    print(f"Access Token: {access_token}")
    print(f"CSRF Token: {csrf_token}")
else:
    print(f"Login failed: {response.json()}")
```

### Making Authenticated Requests

```python
# Use access token in Authorization header
# Use CSRF token in X-CSRF-Token header for POST/PUT/DELETE

headers = {
    "Authorization": f"Bearer {access_token}",
    "X-CSRF-Token": csrf_token
}

# Example: Ingest repository
response = requests.post(
    "https://localhost:8443/ingest",
    json={
        "path": "/path/to/repo",
        "recursive": True
    },
    headers=headers,
    verify=False
)

print(response.json())
```

### Token Refresh

```python
# Refresh access token when it expires
response = requests.post(
    "https://localhost:8443/auth/refresh",
    json={"refresh_token": refresh_token},
    verify=False
)

if response.status_code == 200:
    new_tokens = response.json()
    access_token = new_tokens["access_token"]
    refresh_token = new_tokens["refresh_token"]
```

### Logout

```python
# Logout and revoke tokens
response = requests.post(
    "https://localhost:8443/auth/logout",
    headers={"Authorization": f"Bearer {access_token}"},
    verify=False
)

print(response.json())
```

---

## 2. API Gateway Integration

### Protecting Endpoints with JWT

```python
# services/api_gateway/app.py

from fastapi import Depends
from services.security import get_current_user, require_admin, User

# Require any authenticated user
@app.post("/protected-endpoint")
async def protected_endpoint(
    user: User = Depends(get_current_user)
):
    return {"message": f"Hello {user.username}"}

# Require admin role
@app.post("/admin-endpoint")
async def admin_endpoint(
    user: User = Depends(require_admin)
):
    return {"message": "Admin access granted"}
```

### Adding Rate Limiting

```python
from services.security import check_rate_limit

@app.post("/rate-limited-endpoint")
async def rate_limited_endpoint(
    request: Request,
    _: None = Depends(check_rate_limit)
):
    return {"message": "Request processed"}
```

### Audit Logging

```python
from services.security import get_audit_logger, AuditEventType

@app.post("/important-action")
async def important_action(
    user: User = Depends(get_current_user)
):
    audit_logger = get_audit_logger()
    
    # Log the action
    audit_logger.log_security_event(
        event_type=AuditEventType.API_REQUEST,
        user_id=user.user_id,
        username=user.username,
        client_ip="127.0.0.1",
        details={"action": "important_action"},
        severity="info"
    )
    
    return {"message": "Action logged"}
```

---

## 3. Web Frontend Integration

### React Authentication Hook

```typescript
// web-frontend/src/hooks/useAuth.ts

import { useState, useEffect } from 'react';

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export const useAuth = () => {
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [csrfToken, setCSRFToken] = useState<string>('');

  const login = async (username: string, password: string) => {
    const response = await fetch('https://localhost:8443/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // Important: include cookies
      body: JSON.stringify({ username, password })
    });

    if (response.ok) {
      const data = await response.json();
      setTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token
      });
      
      // CSRF token is in cookie, but also get it from response
      const csrf = response.headers.get('X-CSRF-Token');
      if (csrf) setCSRFToken(csrf);
      
      return true;
    }
    return false;
  };

  const logout = async () => {
    if (!tokens) return;
    
    await fetch('https://localhost:8443/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${tokens.accessToken}`
      },
      credentials: 'include'
    });
    
    setTokens(null);
    setCSRFToken('');
  };

  const makeAuthenticatedRequest = async (
    url: string,
    options: RequestInit = {}
  ) => {
    if (!tokens) throw new Error('Not authenticated');

    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${tokens.accessToken}`,
      'X-CSRF-Token': csrfToken
    };

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include'
    });

    // Handle token expiration
    if (response.status === 401) {
      // Try to refresh token
      const refreshed = await refreshToken();
      if (refreshed) {
        // Retry request with new token
        return makeAuthenticatedRequest(url, options);
      }
    }

    return response;
  };

  const refreshToken = async () => {
    if (!tokens) return false;

    const response = await fetch('https://localhost:8443/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refreshToken })
    });

    if (response.ok) {
      const data = await response.json();
      setTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token
      });
      return true;
    }

    return false;
  };

  return {
    tokens,
    csrfToken,
    login,
    logout,
    makeAuthenticatedRequest,
    isAuthenticated: !!tokens
  };
};
```

### Using the Auth Hook

```typescript
// web-frontend/src/components/LoginForm.tsx

import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

export const LoginForm: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const success = await login(username, password);
    if (success) {
      console.log('Login successful');
    } else {
      console.error('Login failed');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit">Login</button>
    </form>
  );
};
```

### Making API Calls

```typescript
// web-frontend/src/api/client.ts

import { useAuth } from '../hooks/useAuth';

export const useAPI = () => {
  const { makeAuthenticatedRequest } = useAuth();

  const ingestRepository = async (path: string, recursive: boolean = true) => {
    const response = await makeAuthenticatedRequest(
      'https://localhost:8443/ingest',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, recursive })
      }
    );

    return response.json();
  };

  const query = async (query: string, maxTokens: number = 512) => {
    const response = await makeAuthenticatedRequest(
      'https://localhost:8443/query',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, max_tokens: maxTokens })
      }
    );

    return response.json();
  };

  return {
    ingestRepository,
    query
  };
};
```

---

## 4. Terminal Executor Integration

### Command Whitelisting (Planned)

```python
# services/terminal_executor/command_whitelist.py

ALLOWED_COMMANDS = [
    # Git commands
    "git status",
    "git log",
    "git diff",
    "git branch",
    
    # File operations (read-only)
    "ls",
    "cat",
    "head",
    "tail",
    "grep",
    
    # Build commands
    "npm install",
    "npm run build",
    "pip install",
    "cargo build",
    
    # Test commands
    "pytest",
    "npm test",
    "cargo test"
]

def is_command_allowed(command: str) -> bool:
    """Check if command is in whitelist."""
    # Exact match
    if command in ALLOWED_COMMANDS:
        return True
    
    # Prefix match for commands with arguments
    for allowed in ALLOWED_COMMANDS:
        if command.startswith(allowed + " "):
            return True
    
    return False
```

---

## 5. Testing Security Features

### Test Authentication

```bash
# Test login
curl -X POST https://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  -k -c cookies.txt

# Test protected endpoint
curl -X GET https://localhost:8443/auth/me \
  -H "Authorization: Bearer <access_token>" \
  -k -b cookies.txt

# Test CSRF protection
curl -X POST https://localhost:8443/ingest \
  -H "Authorization: Bearer <access_token>" \
  -H "X-CSRF-Token: <csrf_token>" \
  -H "Content-Type: application/json" \
  -d '{"path":"/test","recursive":true}' \
  -k -b cookies.txt
```

### Test Rate Limiting

```bash
# Send 101 requests to trigger rate limit
for i in {1..101}; do
  curl -X GET https://localhost:8443/health -k
done
```

### Test Security Headers

```bash
# Check security headers
curl -I https://localhost:8443/health -k

# Should see:
# Content-Security-Policy: ...
# Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
```

---

## Next Steps

1. Review the [Security Checklist](./SECURITY_CHECKLIST.md)
2. Run `./scripts/setup_security.sh` to generate secrets
3. Deploy with `docker-compose -f docker-compose.secure.yml up -d`
4. Test authentication flow
5. Monitor audit logs

---

**Last Updated:** 2025-01-25

