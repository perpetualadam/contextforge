#!/bin/bash
# Security Setup Script for ContextForge
# Generates TLS certificates and secrets for secure deployment

set -e

echo "🔒 ContextForge Security Setup"
echo "================================"
echo ""

# Create directories
echo "📁 Creating directories..."
mkdir -p secrets
mkdir -p certs
mkdir -p logs

# Generate JWT secret
echo "🔑 Generating JWT secret..."
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/jwt_secret.txt
chmod 600 secrets/jwt_secret.txt

# Generate CSRF secret
echo "🔑 Generating CSRF secret..."
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/csrf_secret.txt
chmod 600 secrets/csrf_secret.txt

# Generate encryption key
echo "🔑 Generating encryption key..."
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())" > secrets/encryption_key.txt
chmod 600 secrets/encryption_key.txt

# Generate database password
echo "🔑 Generating database password..."
python3 -c "import secrets; print(secrets.token_urlsafe(24))" > secrets/db_password.txt
chmod 600 secrets/db_password.txt

# Generate Redis password
echo "🔑 Generating Redis password..."
python3 -c "import secrets; print(secrets.token_urlsafe(24))" > secrets/redis_password.txt
chmod 600 secrets/redis_password.txt

# Create placeholder for API keys (user must fill these)
echo "🔑 Creating API key placeholders..."
touch secrets/openai_api_key.txt
touch secrets/anthropic_api_key.txt
chmod 600 secrets/*.txt

echo ""
echo "⚠️  IMPORTANT: Edit the following files and add your API keys:"
echo "   - secrets/openai_api_key.txt"
echo "   - secrets/anthropic_api_key.txt"
echo ""

# Generate TLS certificates
echo "🔐 Generating TLS certificates..."
echo ""
echo "Choose certificate type:"
echo "  1) Self-signed (for development)"
echo "  2) Let's Encrypt (for production)"
echo ""
read -p "Enter choice [1-2]: " cert_choice

if [ "$cert_choice" = "1" ]; then
    echo ""
    echo "Generating self-signed certificate..."
    
    # Get domain name
    read -p "Enter domain name (default: localhost): " domain
    domain=${domain:-localhost}
    
    # Generate private key
    openssl genrsa -out certs/server.key 2048
    
    # Generate certificate signing request
    openssl req -new -key certs/server.key -out certs/server.csr \
        -subj "/C=US/ST=State/L=City/O=ContextForge/CN=$domain"
    
    # Generate self-signed certificate (valid for 365 days)
    openssl x509 -req -days 365 -in certs/server.csr \
        -signkey certs/server.key -out certs/server.crt
    
    # Set permissions
    chmod 600 certs/server.key
    chmod 644 certs/server.crt
    
    echo "✅ Self-signed certificate generated"
    echo "   Certificate: certs/server.crt"
    echo "   Private key: certs/server.key"
    
elif [ "$cert_choice" = "2" ]; then
    echo ""
    echo "Let's Encrypt setup requires:"
    echo "  - A public domain name"
    echo "  - Port 80 and 443 accessible from the internet"
    echo "  - certbot installed"
    echo ""
    read -p "Enter your domain name: " domain
    
    if command -v certbot &> /dev/null; then
        echo "Running certbot..."
        sudo certbot certonly --standalone -d "$domain"
        
        # Copy certificates
        sudo cp "/etc/letsencrypt/live/$domain/fullchain.pem" certs/server.crt
        sudo cp "/etc/letsencrypt/live/$domain/privkey.pem" certs/server.key
        sudo chown $(whoami):$(whoami) certs/server.*
        chmod 600 certs/server.key
        chmod 644 certs/server.crt
        
        echo "✅ Let's Encrypt certificate installed"
    else
        echo "❌ certbot not found. Install with:"
        echo "   sudo apt-get install certbot  # Debian/Ubuntu"
        echo "   sudo yum install certbot       # RHEL/CentOS"
        exit 1
    fi
else
    echo "❌ Invalid choice"
    exit 1
fi

echo ""
echo "🔒 Security setup complete!"
echo ""
echo "Next steps:"
echo "  1. Review and edit secrets/*.txt files"
echo "  2. Update .env file with security settings"
echo "  3. Run: docker-compose -f docker-compose.secure.yml up -d"
echo ""
echo "Security features enabled:"
echo "  ✅ JWT authentication"
echo "  ✅ CSRF protection"
echo "  ✅ TLS/SSL encryption"
echo "  ✅ Secrets management"
echo "  ✅ Rate limiting"
echo "  ✅ Audit logging"
echo "  ✅ Security headers"
echo "  ✅ Non-root containers"
echo "  ✅ Resource limits"
echo ""

