# How to Test ContextForge Security Features

**Complete step-by-step instructions for running all security tests**

---

## Prerequisites

### 1. Install Docker Desktop (Windows)

1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
2. Install Docker Desktop
3. **Start Docker Desktop** (very important!)
4. Wait for Docker to fully start (whale icon in system tray should be steady)
5. Verify Docker is running:
   ```powershell
   docker --version
   docker ps
   ```

### 2. Install Python Dependencies

```powershell
# Install pytest and requests
pip install pytest requests

# Verify installation
pytest --version
```

---

## Step-by-Step Testing Instructions

### Step 1: Start Docker Desktop

**CRITICAL: Docker Desktop MUST be running!**

1. Open Docker Desktop application
2. Wait for it to say "Docker Desktop is running"
3. Check system tray - whale icon should be steady (not animated)

### Step 2: Navigate to Project Directory

```powershell
cd C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge
```

### Step 3: Generate Security Secrets (First Time Only)

```powershell
# Run security setup script
.\scripts\setup_security.ps1

# This creates:
# - secrets/jwt_secret.txt
# - secrets/csrf_secret.txt
# - secrets/db_password.txt
# - secrets/redis_password.txt
# - certs/server.crt
# - certs/server.key
```

### Step 4: Start All Services

```powershell
# Start services in background
docker-compose -f docker-compose.secure.yml up -d

# Wait 30 seconds for services to initialize
Start-Sleep -Seconds 30

# Check services are running
docker-compose -f docker-compose.secure.yml ps
```

**Expected output:**
```
NAME                    STATUS
contextforge-api        Up
contextforge-postgres   Up
contextforge-redis      Up
contextforge-terminal   Up
```

### Step 5: Verify Services Are Healthy

```powershell
# Test API Gateway health endpoint
curl.exe -k https://localhost:8443/health

# Expected output: {"status":"healthy"}
```

If you get an error:
- Wait another 30 seconds and try again
- Check logs: `docker-compose -f docker-compose.secure.yml logs api_gateway`

### Step 6: Run Individual Test Suites

**Test 1: Integration Tests**
```powershell
pytest tests/security/test_integration.py -v --tb=short
```

**Test 2: Cookie Authentication Tests**
```powershell
pytest tests/security/test_cookie_auth.py -v --tb=short
```

**Test 3: Terminal Sandbox Tests**
```powershell
pytest tests/security/test_terminal_sandbox.py -v --tb=short
```

**Test 4: File Validation Tests**
```powershell
pytest tests/security/test_file_validation.py -v --tb=short
```

### Step 7: Run All Tests Together

```powershell
# Run complete test suite
.\scripts\run_all_tests.ps1
```

**OR manually:**
```powershell
pytest tests/security/ -v --tb=short
```

---

## Understanding Test Output

### Successful Test Output

```
tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie PASSED [12%]
tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_returns_tokens PASSED [25%]
...

========================================
Overall: 4/4 test suites passed
========================================

🎉 All tests passed! Ready for deployment.
```

### Failed Test Output

```
tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie FAILED [12%]

FAILED tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie
AssertionError: assert 'csrf_token' in {}
```

**What to do if tests fail:**
1. Check if services are running: `docker-compose -f docker-compose.secure.yml ps`
2. Check service logs: `docker-compose -f docker-compose.secure.yml logs`
3. Restart services: `docker-compose -f docker-compose.secure.yml restart`
4. Run tests again

---

## Troubleshooting

### Problem: "Docker is not running"

**Solution:**
1. Open Docker Desktop application
2. Wait for it to fully start
3. Verify: `docker ps` should work without errors

### Problem: "Connection refused" or "Cannot connect to localhost:8443"

**Solution:**
```powershell
# Check if services are running
docker-compose -f docker-compose.secure.yml ps

# If not running, start them
docker-compose -f docker-compose.secure.yml up -d

# Wait 30 seconds
Start-Sleep -Seconds 30

# Try again
curl.exe -k https://localhost:8443/health
```

### Problem: "Port 8443 already in use"

**Solution:**
```powershell
# Find what's using port 8443
netstat -ano | findstr :8443

# Stop the conflicting service or change port in .env
```

### Problem: "pytest: command not found"

**Solution:**
```powershell
# Install pytest
pip install pytest requests

# Verify
pytest --version
```

### Problem: Tests are skipped

**Reason:** Services are not running or not accessible

**Solution:**
1. Ensure Docker Desktop is running
2. Start services: `docker-compose -f docker-compose.secure.yml up -d`
3. Wait 30 seconds
4. Run tests again

---

## Quick Reference Commands

### Start Services
```powershell
docker-compose -f docker-compose.secure.yml up -d
```

### Check Service Status
```powershell
docker-compose -f docker-compose.secure.yml ps
```

### View Logs
```powershell
# All services
docker-compose -f docker-compose.secure.yml logs

# Specific service
docker-compose -f docker-compose.secure.yml logs api_gateway

# Follow logs (live)
docker-compose -f docker-compose.secure.yml logs -f
```

### Stop Services
```powershell
docker-compose -f docker-compose.secure.yml down
```

### Restart Services
```powershell
docker-compose -f docker-compose.secure.yml restart
```

### Run All Tests
```powershell
.\scripts\run_all_tests.ps1
```

### Run Specific Test
```powershell
pytest tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie -v
```

---

## After Tests Pass

Once all tests pass, you can deploy to GitHub:

```powershell
# Automated deployment
.\scripts\deploy_to_github.ps1

# OR manual deployment
git add .
git commit -m "feat: Complete security hardening with optional enhancements"
git push origin master
```

---

## Summary Checklist

- [ ] Docker Desktop is installed and running
- [ ] Python and pytest are installed
- [ ] Navigated to project directory
- [ ] Generated security secrets (first time only)
- [ ] Started services with `docker-compose up -d`
- [ ] Waited 30 seconds for services to initialize
- [ ] Verified health endpoint: `curl.exe -k https://localhost:8443/health`
- [ ] Ran test suite: `.\scripts\run_all_tests.ps1`
- [ ] All tests passed ✅
- [ ] Ready to deploy to GitHub

---

**Need Help?**

Check the logs:
```powershell
docker-compose -f docker-compose.secure.yml logs
```

Or restart everything:
```powershell
docker-compose -f docker-compose.secure.yml down
docker-compose -f docker-compose.secure.yml up -d
Start-Sleep -Seconds 30
.\scripts\run_all_tests.ps1
```

