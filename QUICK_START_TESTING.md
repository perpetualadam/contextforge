# Quick Start - Testing & Deployment

**The fastest way to test and deploy ContextForge security features**

---

## 🚀 One-Command Test and Deploy

### Prerequisites
1. **Start Docker Desktop** (MUST be running!)
2. Open PowerShell in project directory

### Run Everything Automatically

```powershell
.\TEST_AND_DEPLOY.ps1
```

This single command will:
1. ✅ Check Docker is running
2. ✅ Install pytest if needed
3. ✅ Start all services
4. ✅ Wait for services to be healthy
5. ✅ Run all 37 security tests
6. ✅ Commit changes
7. ✅ Push to GitHub

**That's it!** ☕ Grab a coffee and wait ~2-3 minutes.

---

## 📋 Step-by-Step (Manual)

If you prefer to run each step manually:

### 1. Start Docker Desktop
- Open Docker Desktop application
- Wait for it to say "Docker Desktop is running"

### 2. Start Services
```powershell
docker-compose -f docker-compose.secure.yml up -d
Start-Sleep -Seconds 30
```

### 3. Verify Services
```powershell
curl.exe -k https://localhost:8443/health
# Should return: {"status":"healthy"}
```

### 4. Run Tests
```powershell
pytest tests/security/ -v
```

### 5. Deploy to GitHub
```powershell
git add .
git commit -m "feat: Complete security hardening"
git push origin master
```

---

## 🧪 Test Options

### Run All Tests
```powershell
pytest tests/security/ -v
```

### Run Specific Test Suite
```powershell
# Cookie authentication tests
pytest tests/security/test_cookie_auth.py -v

# Terminal sandbox tests
pytest tests/security/test_terminal_sandbox.py -v

# File validation tests
pytest tests/security/test_file_validation.py -v

# Integration tests
pytest tests/security/test_integration.py -v
```

### Run Single Test
```powershell
pytest tests/security/test_cookie_auth.py::TestCookieAuthentication::test_login_sets_csrf_cookie -v
```

---

## 🔧 Troubleshooting

### Docker Not Running
```
❌ Docker is not running
```
**Solution:** Start Docker Desktop and wait for it to fully start

### Services Not Starting
```
❌ Services failed to start properly
```
**Solution:**
```powershell
docker-compose -f docker-compose.secure.yml logs
docker-compose -f docker-compose.secure.yml restart
```

### Tests Failing
```
❌ Some tests failed
```
**Solution:**
1. Check services are running: `docker-compose -f docker-compose.secure.yml ps`
2. Check logs: `docker-compose -f docker-compose.secure.yml logs`
3. Restart services: `docker-compose -f docker-compose.secure.yml restart`
4. Run tests again

### Port Already in Use
```
Error: port 8443 already in use
```
**Solution:**
```powershell
# Find what's using the port
netstat -ano | findstr :8443

# Stop the conflicting service
```

---

## 📊 What Gets Tested

### 37 Security Tests Across 4 Suites

1. **Integration Tests** (13 tests)
   - JWT authentication
   - CSRF protection
   - Rate limiting
   - Security headers
   - TLS configuration
   - Audit logging

2. **Cookie Authentication** (8 tests)
   - HTTP-only cookies
   - CSRF tokens
   - Token refresh
   - Logout functionality

3. **Terminal Sandbox** (7 tests)
   - Sandbox validation
   - Directory restrictions
   - Command whitelist
   - Audit logging

4. **File Validation** (9 tests)
   - File type validation
   - File size limits
   - CSRF protection
   - Authentication

---

## 📦 What Gets Deployed

When you run `.\TEST_AND_DEPLOY.ps1`, it commits and pushes:

- ✅ 20+ new security files
- ✅ 5+ modified files
- ✅ Complete test suite (37 tests)
- ✅ Documentation (6 guides)
- ✅ Deployment scripts

**Commit message includes:**
- Feature summary
- Security features list
- Test results

---

## ⚡ Quick Commands Reference

```powershell
# One command to do everything
.\TEST_AND_DEPLOY.ps1

# Just run tests (skip deploy)
.\TEST_AND_DEPLOY.ps1 -SkipDeploy

# Just deploy (skip tests) - NOT RECOMMENDED
.\TEST_AND_DEPLOY.ps1 -SkipTests

# Start services
docker-compose -f docker-compose.secure.yml up -d

# Stop services
docker-compose -f docker-compose.secure.yml down

# View logs
docker-compose -f docker-compose.secure.yml logs -f

# Run all tests
pytest tests/security/ -v

# Check service status
docker-compose -f docker-compose.secure.yml ps
```

---

## ✅ Success Checklist

Before running tests:
- [ ] Docker Desktop is running
- [ ] In project directory: `C:\Users\Brian\OneDrive\Documents\augment-projects\ContextForge`

After running `.\TEST_AND_DEPLOY.ps1`:
- [ ] All services started ✅
- [ ] All 37 tests passed ✅
- [ ] Changes committed ✅
- [ ] Pushed to GitHub ✅

---

## 🎯 Expected Output

```powershell
PS> .\TEST_AND_DEPLOY.ps1

=========================================
ContextForge - Test and Deploy
=========================================

Step 1: Checking Docker...
✅ Docker is running

Step 2: Checking pytest...
✅ pytest is installed

Step 3: Starting services...
✅ Services are already running

Step 4: Verifying services...
✅ API Gateway is healthy

Step 5: Running tests...

tests/security/test_integration.py::TestAuthentication::test_login_success PASSED
tests/security/test_integration.py::TestAuthentication::test_login_failure PASSED
...
tests/security/test_file_validation.py::TestFileValidation::test_csrf_token_in_upload_request PASSED

=========================================
✅ All tests passed!
=========================================

Step 6: Deploying to GitHub...

📝 Uncommitted changes detected
✅ Changes committed

Pushing to GitHub...

=========================================
✅ Successfully deployed to GitHub!
=========================================

Branch: master
Repository: https://github.com/perpetualadam/contextforge

🎉 All done!
```

---

## 📚 More Information

- **Detailed Testing Guide:** `HOW_TO_TEST.md`
- **Deployment Guide:** `docs/DEPLOYMENT_GUIDE.md`
- **Testing & Deployment:** `docs/TESTING_AND_DEPLOYMENT.md`
- **Implementation Status:** `docs/IMPLEMENTATION_STATUS.md`

---

**Ready? Let's go!** 🚀

```powershell
.\TEST_AND_DEPLOY.ps1
```

