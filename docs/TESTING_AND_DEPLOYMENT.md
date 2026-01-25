# Testing and Deployment Guide

Complete guide for testing security features and deploying to GitHub.

---

## Table of Contents

1. [Test Suites](#test-suites)
2. [Running Tests](#running-tests)
3. [Test Results](#test-results)
4. [Deployment to GitHub](#deployment-to-github)
5. [Troubleshooting](#troubleshooting)

---

## Test Suites

### 1. Integration Tests (`test_integration.py`)

Tests core security infrastructure:
- ✅ JWT Authentication (login, logout, token refresh)
- ✅ CSRF Protection (POST with/without tokens)
- ✅ Rate Limiting (100 requests per 60 seconds)
- ✅ Security Headers (CSP, HSTS, X-Frame-Options, etc.)
- ✅ TLS Configuration (HTTPS, TLS 1.2+)
- ✅ Audit Logging (log file creation and content)

### 2. Cookie Authentication Tests (`test_cookie_auth.py`)

Tests HTTP-only cookie implementation:
- ✅ Login sets CSRF cookie
- ✅ Tokens returned in response
- ✅ Cookie security attributes
- ✅ Authenticated requests with cookies
- ✅ CSRF protection on POST requests
- ✅ Logout clears session
- ✅ Token refresh flow

### 3. Terminal Sandbox Tests (`test_terminal_sandbox.py`)

Tests terminal executor hardening:
- ✅ Sandbox configuration endpoint
- ✅ Commands in allowed directories
- ✅ Commands blocked in disallowed directories
- ✅ Directory traversal prevention
- ✅ Command whitelist endpoint
- ✅ Audit logging for commands
- ✅ Blocked commands logged

### 4. File Validation Tests (`test_file_validation.py`)

Tests file upload security:
- ✅ Allowed file types (JPEG, PNG, PDF, text)
- ✅ File upload requires CSRF token
- ✅ File upload requires authentication
- ✅ Client-side file size validation (50 MB)
- ✅ Client-side file type validation
- ✅ CSRF token in upload requests

---

## Running Tests

### Prerequisites

1. **Install pytest:**
   ```bash
   pip install pytest requests
   ```

2. **Start services:**
   ```bash
   docker-compose -f docker-compose.secure.yml up -d
   ```

3. **Wait for services to be ready:**
   ```bash
   # Check health endpoint
   curl -k https://localhost:8443/health
   ```

### Run All Tests

**Linux/Mac:**
```bash
chmod +x scripts/run_all_tests.sh
./scripts/run_all_tests.sh
```

**Windows:**
```powershell
.\scripts\run_all_tests.ps1
```

### Run Individual Test Suites

**Integration Tests:**
```bash
pytest tests/security/test_integration.py -v
```

**Cookie Authentication Tests:**
```bash
pytest tests/security/test_cookie_auth.py -v
```

**Terminal Sandbox Tests:**
```bash
pytest tests/security/test_terminal_sandbox.py -v
```

**File Validation Tests:**
```bash
pytest tests/security/test_file_validation.py -v
```

### Run Specific Test

```bash
pytest tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie -v
```

---

## Test Results

### Expected Output

```
========================================
ContextForge Complete Test Suite
========================================

✅ Services are running

========================================
Running Test Suites
========================================

1. Running Integration Tests...
   - JWT Authentication
   - CSRF Protection
   - Rate Limiting
   - Security Headers
   - TLS Configuration
   - Audit Logging

test_integration.py::TestAuthentication::test_login_success PASSED
test_integration.py::TestAuthentication::test_login_failure PASSED
test_integration.py::TestAuthentication::test_protected_endpoint_without_auth PASSED
test_integration.py::TestAuthentication::test_protected_endpoint_with_auth PASSED
test_integration.py::TestAuthentication::test_token_refresh PASSED
test_integration.py::TestCSRFProtection::test_post_without_csrf_token PASSED
test_integration.py::TestCSRFProtection::test_post_with_csrf_token PASSED
test_integration.py::TestRateLimiting::test_rate_limit_exceeded PASSED
test_integration.py::TestSecurityHeaders::test_security_headers_present PASSED
test_integration.py::TestTLSConfiguration::test_https_connection PASSED
test_integration.py::TestTLSConfiguration::test_tls_version PASSED
test_integration.py::TestAuditLogging::test_audit_log_file_exists PASSED
test_integration.py::TestAuditLogging::test_audit_log_contains_events PASSED

========================================
Test Results Summary
========================================

✅ Integration Tests: PASSED
✅ Cookie Authentication Tests: PASSED
✅ Terminal Sandbox Tests: PASSED
✅ File Validation Tests: PASSED

========================================
Overall: 4/4 test suites passed
========================================

🎉 All tests passed! Ready for deployment.
```

### Interpreting Results

- **PASSED** - Test succeeded ✅
- **FAILED** - Test failed, review error message ❌
- **SKIPPED** - Test skipped (feature not available) ⏭️
- **ERROR** - Test encountered an error ⚠️

---

## Deployment to GitHub

### Automated Deployment

**Linux/Mac:**
```bash
chmod +x scripts/deploy_to_github.sh
./scripts/deploy_to_github.sh
```

**Windows:**
```powershell
.\scripts\deploy_to_github.ps1
```

The script will:
1. Check for uncommitted changes
2. Prompt for commit message (or use default)
3. Commit all changes
4. Push to GitHub
5. Provide next steps

### Manual Deployment

```bash
# 1. Check status
git status

# 2. Add all changes
git add .

# 3. Commit with message
git commit -m "feat: Complete security hardening with optional enhancements"

# 4. Push to GitHub
git push origin master

# 5. Create Pull Request (if using feature branch)
# Visit: https://github.com/perpetualadam/contextforge/pulls
```

### Default Commit Message

The deployment script uses this commit message by default:

```
feat: Complete security hardening with optional enhancements

- Implemented HTTP-only cookie authentication (removed localStorage)
- Added terminal executor sandbox validation and command whitelist
- Implemented frontend file type/size validation with CSRF protection
- Added Let's Encrypt integration for production TLS certificates
- Created comprehensive integration test suite
- Added deployment documentation and guides

Security Features:
- JWT authentication with RBAC
- CSRF protection for all state-changing requests
- Distributed rate limiting with Redis
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Audit logging for all security events
- Container security (non-root, resource limits)
- TLS/SSL with automatic certificate renewal

Tests:
- Integration tests for all security features
- Cookie authentication tests
- Terminal sandbox validation tests
- File upload validation tests
```

---

## Troubleshooting

### Tests Failing

**Services not running:**
```bash
docker-compose -f docker-compose.secure.yml up -d
docker-compose -f docker-compose.secure.yml ps
```

**Port conflicts:**
```bash
# Check what's using port 8443
lsof -i :8443  # Linux/Mac
netstat -ano | findstr :8443  # Windows

# Stop conflicting service or change port in .env
```

**SSL certificate errors:**
```bash
# Use -k flag with curl to skip verification
curl -k https://localhost:8443/health

# Or set VERIFY_SSL=False in test files (already set)
```

### Deployment Failing

**Authentication required:**
```bash
# Configure GitHub credentials
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Use personal access token
git remote set-url origin https://YOUR_TOKEN@github.com/perpetualadam/contextforge.git
```

**Branch protection:**
```bash
# Create feature branch instead
git checkout -b feature/security-hardening
git push origin feature/security-hardening

# Then create PR on GitHub
```

**Network issues:**
```bash
# Check internet connection
ping github.com

# Check git remote
git remote -v
```

---

## Next Steps After Deployment

1. **Visit GitHub Repository:**
   - https://github.com/perpetualadam/contextforge

2. **Create Pull Request** (if using feature branch):
   - Review changes
   - Request reviews
   - Merge when approved

3. **Tag Release:**
   ```bash
   git tag -a v1.0.0-security -m "Security hardening release"
   git push origin v1.0.0-security
   ```

4. **Update Documentation:**
   - Update README.md with security features
   - Add security badge
   - Link to security documentation

---

**Last Updated:** 2025-01-25

