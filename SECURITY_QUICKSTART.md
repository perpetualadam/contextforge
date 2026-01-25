# ContextForge Security Quick Start

Get ContextForge running with full security hardening in 5 minutes.

---

## Prerequisites

- Docker and Docker Compose installed
- OpenSSL installed (for certificate generation)
- Python 3.8+ (for secret generation)

---

## Step 1: Generate Secrets (2 minutes)

### Linux/Mac
```bash
chmod +x scripts/setup_security.sh
./scripts/setup_security.sh
```

### Windows (PowerShell)
```powershell
.\scripts\setup_security.ps1
```

**What this does:**
- Generates JWT secret, CSRF secret, encryption key
- Generates database and Redis passwords
- Creates TLS certificates (self-signed for development)
- Sets proper file permissions

**Important:** Edit these files and add your API keys:
- `secrets/openai_api_key.txt`
- `secrets/anthropic_api_key.txt`

---

## Step 2: Review Configuration (1 minute)

Check `docker-compose.secure.yml` and verify:
- [ ] Port 8443 is available
- [ ] Secrets paths are correct
- [ ] Resource limits are appropriate for your system

---

## Step 3: Deploy (1 minute)

```bash
docker-compose -f docker-compose.secure.yml up -d
```

**Services started:**
- API Gateway (HTTPS on port 8443)
- Vector Index
- Preprocessor
- Connector
- Web Fetcher
- Terminal Executor
- Redis (with password)
- PostgreSQL (with password)
- Persistence Service

---

## Step 4: Verify Deployment (1 minute)

### Check Services
```bash
docker-compose -f docker-compose.secure.yml ps
```

All services should show "Up" status.

### Test HTTPS
```bash
curl -k https://localhost:8443/health
```

Expected response:
```json
{
  "status": "healthy",
  "services": {...}
}
```

### Test Authentication
```bash
# Login (use your actual credentials)
curl -X POST https://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}' \
  -k -c cookies.txt

# Should return:
# {
#   "access_token": "eyJ...",
#   "refresh_token": "eyJ...",
#   "token_type": "bearer"
# }
```

### Test Security Headers
```bash
curl -I https://localhost:8443/health -k
```

Should see headers:
- `Content-Security-Policy`
- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`

---

## Step 5: Create First User (Optional)

Currently using demo users. To create a real user, you'll need to:

1. Hash a password:
```python
from services.security import get_jwt_manager

jwt_manager = get_jwt_manager()
password_hash = jwt_manager.hash_password("your_secure_password")
print(password_hash)
```

2. Update `services/api_gateway/auth_routes.py` DEMO_USERS dict with your user

---

## Security Features Enabled

✅ **JWT Authentication** - All endpoints protected  
✅ **TLS/SSL** - HTTPS on port 8443  
✅ **CSRF Protection** - State-changing requests protected  
✅ **Rate Limiting** - 100 requests per 60 seconds  
✅ **Security Headers** - CSP, HSTS, X-Frame-Options, etc.  
✅ **Audit Logging** - All requests logged  
✅ **Secrets Management** - Docker secrets for sensitive data  
✅ **Container Security** - Non-root, resource limits, capability dropping  
✅ **SQL Injection Prevention** - Parameterized queries  
✅ **Password Hashing** - Argon2id with bcrypt fallback  

---

## Common Issues

### Issue: "TLS certificate not found"
**Solution:** Run `./scripts/setup_security.sh` to generate certificates

### Issue: "Permission denied" on secrets
**Solution:** 
```bash
chmod 600 secrets/*.txt
chmod 644 certs/server.crt
chmod 600 certs/server.key
```

### Issue: "Redis connection failed"
**Solution:** Verify Redis password in `secrets/redis_password.txt` matches Docker Compose configuration

### Issue: "PostgreSQL authentication failed"
**Solution:** Verify database password in `secrets/db_password.txt`

---

## Next Steps

1. **Review Security Checklist**
   - See `docs/SECURITY_CHECKLIST.md` for complete feature list

2. **Read Integration Guide**
   - See `docs/SECURITY_INTEGRATION.md` for code examples

3. **Configure Web Frontend**
   - Update frontend to use HTTPS
   - Implement cookie-based authentication

4. **Set Up Monitoring**
   - Monitor audit logs: `./logs/audit.log`
   - Check security status: `GET /security/status`

5. **Production Deployment**
   - Replace self-signed certificates with Let's Encrypt
   - Update `ALLOWED_ORIGINS` in `.env`
   - Enable HSTS preload
   - Set up log rotation

---

## Useful Commands

### View Logs
```bash
# All services
docker-compose -f docker-compose.secure.yml logs -f

# Specific service
docker-compose -f docker-compose.secure.yml logs -f api_gateway

# Audit logs
tail -f logs/audit.log
```

### Restart Services
```bash
docker-compose -f docker-compose.secure.yml restart
```

### Stop Services
```bash
docker-compose -f docker-compose.secure.yml down
```

### Update Secrets
```bash
# 1. Update secret file
echo "new_secret_value" > secrets/jwt_secret.txt

# 2. Restart affected services
docker-compose -f docker-compose.secure.yml restart api_gateway
```

---

## Security Endpoints

- `POST /auth/login` - Authenticate and get JWT tokens
- `POST /auth/logout` - Logout and revoke tokens
- `POST /auth/refresh` - Refresh access token
- `GET /auth/csrf-token` - Get CSRF token
- `GET /auth/me` - Get current user info
- `POST /auth/change-password` - Change password
- `GET /security/status` - Security status and statistics
- `GET /security/report` - Comprehensive security report

---

## Support

- **Documentation:** `docs/` directory
- **Security Module:** `services/security/README.md`
- **Issues:** Check audit logs and Docker logs

---

**Ready to go!** 🚀

Your ContextForge instance is now running with enterprise-grade security.

