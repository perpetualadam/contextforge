# ContextForge Secure Deployment Guide

Complete guide for deploying ContextForge with full security hardening.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Verification](#verification)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Docker 20.10+ and Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 10GB disk space
- Linux, macOS, or Windows with WSL2

### Network Requirements
- Port 8443 (HTTPS API Gateway)
- Port 80 (HTTP redirect, Let's Encrypt validation)
- Port 3000 (Web Frontend - optional)

---

## Development Deployment

### 1. Generate Secrets and Certificates

**Linux/Mac:**
```bash
chmod +x scripts/setup_security.sh
./scripts/setup_security.sh
```

**Windows:**
```powershell
.\scripts\setup_security.ps1
```

This generates:
- JWT secret
- CSRF secret
- Database and Redis passwords
- Self-signed TLS certificates
- Encryption keys

### 2. Configure API Keys

Edit the following files and add your API keys:

```bash
# OpenAI API Key (optional)
echo "your-openai-api-key" > secrets/openai_api_key.txt

# Anthropic API Key (optional)
echo "your-anthropic-api-key" > secrets/anthropic_api_key.txt
```

### 3. Review Configuration

Check `docker-compose.secure.yml` and `.env` files:

```bash
# Verify secrets are generated
ls -la secrets/

# Check environment variables
cat .env
```

### 4. Deploy Services

```bash
docker-compose -f docker-compose.secure.yml up -d
```

### 5. Verify Deployment

```bash
# Check all services are running
docker-compose -f docker-compose.secure.yml ps

# Test HTTPS endpoint
curl -k https://localhost:8443/health

# View logs
docker-compose -f docker-compose.secure.yml logs -f api_gateway
```

---

## Production Deployment

### 1. Domain and DNS Setup

1. Register a domain name (e.g., `contextforge.example.com`)
2. Point DNS A record to your server's IP address
3. Wait for DNS propagation (can take up to 48 hours)

### 2. Obtain Let's Encrypt Certificate

**Linux/Mac:**
```bash
sudo chmod +x scripts/setup_letsencrypt.sh
sudo ./scripts/setup_letsencrypt.sh
```

**Windows:**
```powershell
# Run as Administrator
.\scripts\setup_letsencrypt.ps1
```

Follow the prompts to:
- Enter your domain name
- Enter your email address
- Obtain SSL certificate

### 3. Configure Firewall

**Linux (UFW):**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8443/tcp
sudo ufw enable
```

**Linux (iptables):**
```bash
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8443 -j ACCEPT
sudo iptables-save
```

**Windows:**
```powershell
New-NetFirewallRule -DisplayName "HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
New-NetFirewallRule -DisplayName "ContextForge API" -Direction Inbound -Protocol TCP -LocalPort 8443 -Action Allow
```

### 4. Update Environment Variables

Edit `.env` file:

```bash
# Production settings
TLS_ENABLED=true
ALLOWED_ORIGINS=https://contextforge.example.com
RATE_LIMIT_ENABLED=true
AUDIT_LOG_ENABLED=true

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=contextforge

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
```

### 5. Deploy to Production

```bash
# Pull latest images
docker-compose -f docker-compose.secure.yml pull

# Deploy
docker-compose -f docker-compose.secure.yml up -d

# Check logs
docker-compose -f docker-compose.secure.yml logs -f
```

### 6. Set Up Monitoring

```bash
# View audit logs
tail -f logs/audit.log

# Monitor container health
watch docker-compose -f docker-compose.secure.yml ps

# Check resource usage
docker stats
```

---

## Verification

### 1. Run Security Tests

```bash
# Linux/Mac
chmod +x scripts/run_security_tests.sh
./scripts/run_security_tests.sh

# Windows
.\scripts\run_security_tests.ps1
```

### 2. Manual Verification

**Test HTTPS:**
```bash
curl -k https://localhost:8443/health
```

**Test Authentication:**
```bash
# Login
curl -X POST https://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  -k -c cookies.txt

# Get user info
curl -X GET https://localhost:8443/auth/me \
  -H "Authorization: Bearer <access_token>" \
  -k -b cookies.txt
```

**Test Security Headers:**
```bash
curl -I https://localhost:8443/health -k | grep -E "(Content-Security-Policy|Strict-Transport-Security|X-Frame-Options)"
```

**Test Rate Limiting:**
```bash
# Send 101 requests
for i in {1..101}; do curl -k https://localhost:8443/health; done
```

---

## Troubleshooting

### Services Not Starting

**Check logs:**
```bash
docker-compose -f docker-compose.secure.yml logs
```

**Common issues:**
- Port already in use: `docker ps` to find conflicting containers
- Secrets not found: Run `./scripts/setup_security.sh`
- Permission denied: Check file permissions on secrets (should be 600)

### TLS Certificate Errors

**Self-signed certificate warnings:**
- Expected in development
- Use `-k` flag with curl
- Add exception in browser

**Let's Encrypt failures:**
- Verify DNS is pointing to server
- Check port 80 is accessible
- Ensure domain is correct

### Authentication Failures

**Invalid credentials:**
- Default: admin / admin123
- Check `services/api_gateway/auth_routes.py` for demo users

**Token expired:**
- Access tokens expire after 60 minutes
- Use refresh token to get new access token

### Rate Limiting Issues

**Too many requests:**
- Default: 100 requests per 60 seconds
- Adjust in `.env`: `RATE_LIMIT_REQUESTS=200`
- Wait 60 seconds for window to reset

### Database Connection Errors

**PostgreSQL not accessible:**
```bash
# Check PostgreSQL is running
docker-compose -f docker-compose.secure.yml ps postgres

# Check password matches
cat secrets/db_password.txt

# Test connection
docker-compose -f docker-compose.secure.yml exec postgres psql -U contextforge -d contextforge
```

---

## Maintenance

### Backup

```bash
# Backup database
docker-compose -f docker-compose.secure.yml exec postgres pg_dump -U contextforge contextforge > backup.sql

# Backup secrets
tar -czf secrets-backup.tar.gz secrets/

# Backup certificates
tar -czf certs-backup.tar.gz certs/
```

### Updates

```bash
# Pull latest changes
git pull

# Rebuild images
docker-compose -f docker-compose.secure.yml build

# Restart services
docker-compose -f docker-compose.secure.yml up -d
```

### Certificate Renewal

**Automatic (Linux):**
- Configured by `setup_letsencrypt.sh`
- Runs daily via cron

**Manual:**
```bash
sudo certbot renew
sudo ./scripts/setup_letsencrypt.sh
docker-compose -f docker-compose.secure.yml restart api_gateway
```

---

## Support

- **Documentation:** `docs/` directory
- **Security:** `docs/SECURITY_CHECKLIST.md`
- **Integration:** `docs/SECURITY_INTEGRATION.md`
- **Quick Start:** `SECURITY_QUICKSTART.md`

---

**Last Updated:** 2025-01-25

