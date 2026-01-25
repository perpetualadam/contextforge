#!/bin/bash
# Setup Let's Encrypt certificates for ContextForge production deployment
# This script uses certbot to obtain and configure SSL certificates

set -e

echo "========================================="
echo "ContextForge Let's Encrypt Setup"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Certbot not found. Installing..."
    
    # Detect OS and install certbot
    if [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        apt-get update
        apt-get install -y certbot
    elif [ -f /etc/redhat-release ]; then
        # RHEL/CentOS/Fedora
        yum install -y certbot
    else
        echo "ERROR: Unsupported OS. Please install certbot manually."
        exit 1
    fi
fi

# Get domain name
read -p "Enter your domain name (e.g., contextforge.example.com): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo "ERROR: Domain name is required"
    exit 1
fi

# Get email for Let's Encrypt notifications
read -p "Enter your email address for Let's Encrypt notifications: " EMAIL
if [ -z "$EMAIL" ]; then
    echo "ERROR: Email address is required"
    exit 1
fi

# Create certs directory if it doesn't exist
CERTS_DIR="./certs"
mkdir -p "$CERTS_DIR"

echo ""
echo "Obtaining Let's Encrypt certificate for $DOMAIN..."
echo ""

# Obtain certificate using standalone mode
# This requires port 80 to be available
certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --domains "$DOMAIN" \
    --preferred-challenges http

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to obtain certificate"
    echo ""
    echo "Common issues:"
    echo "1. Port 80 is not accessible from the internet"
    echo "2. DNS is not pointing to this server"
    echo "3. Firewall is blocking port 80"
    echo ""
    echo "Alternative: Use DNS challenge instead:"
    echo "  certbot certonly --manual --preferred-challenges dns -d $DOMAIN"
    exit 1
fi

# Copy certificates to certs directory
CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
cp "$CERT_PATH/fullchain.pem" "$CERTS_DIR/server.crt"
cp "$CERT_PATH/privkey.pem" "$CERTS_DIR/server.key"

# Set proper permissions
chmod 644 "$CERTS_DIR/server.crt"
chmod 600 "$CERTS_DIR/server.key"

echo ""
echo "✅ Certificates obtained and copied successfully!"
echo ""
echo "Certificate: $CERTS_DIR/server.crt"
echo "Private Key: $CERTS_DIR/server.key"
echo ""

# Setup automatic renewal
echo "Setting up automatic certificate renewal..."

# Create renewal script
cat > /etc/cron.daily/certbot-renew << 'EOF'
#!/bin/bash
# Renew Let's Encrypt certificates and restart ContextForge

certbot renew --quiet

# Copy renewed certificates
DOMAIN=$(certbot certificates | grep "Domains:" | head -1 | awk '{print $2}')
CERT_PATH="/etc/letsencrypt/live/$DOMAIN"
CERTS_DIR="/path/to/contextforge/certs"

if [ -f "$CERT_PATH/fullchain.pem" ]; then
    cp "$CERT_PATH/fullchain.pem" "$CERTS_DIR/server.crt"
    cp "$CERT_PATH/privkey.pem" "$CERTS_DIR/server.key"
    chmod 644 "$CERTS_DIR/server.crt"
    chmod 600 "$CERTS_DIR/server.key"
    
    # Restart ContextForge services
    cd /path/to/contextforge
    docker-compose -f docker-compose.secure.yml restart api_gateway
fi
EOF

# Update the paths in the renewal script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
sed -i "s|/path/to/contextforge|$PROJECT_DIR|g" /etc/cron.daily/certbot-renew

chmod +x /etc/cron.daily/certbot-renew

echo "✅ Automatic renewal configured (daily check)"
echo ""

# Update .env file
if [ -f .env ]; then
    # Update or add TLS_ENABLED
    if grep -q "^TLS_ENABLED=" .env; then
        sed -i 's/^TLS_ENABLED=.*/TLS_ENABLED=true/' .env
    else
        echo "TLS_ENABLED=true" >> .env
    fi
    
    echo "✅ Updated .env file with TLS_ENABLED=true"
fi

echo ""
echo "========================================="
echo "Let's Encrypt Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Update your DNS to point $DOMAIN to this server"
echo "2. Ensure ports 80 and 443 are open in your firewall"
echo "3. Deploy ContextForge with: docker-compose -f docker-compose.secure.yml up -d"
echo "4. Access ContextForge at: https://$DOMAIN:8443"
echo ""
echo "Certificate will auto-renew every 60 days"
echo ""

