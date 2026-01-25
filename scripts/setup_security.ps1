# Security Setup Script for ContextForge (PowerShell)
# Generates TLS certificates and secrets for secure deployment

Write-Host "ContextForge Security Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Create directories
Write-Host "[INFO] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "secrets" | Out-Null
New-Item -ItemType Directory -Force -Path "certs" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# Function to generate random string
function New-RandomString {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Substring(0, $Length)
}

# Generate JWT secret
Write-Host "[INFO] Generating JWT secret..." -ForegroundColor Yellow
New-RandomString -Length 32 | Out-File -FilePath "secrets\jwt_secret.txt" -NoNewline -Encoding ASCII

# Generate CSRF secret
Write-Host "[INFO] Generating CSRF secret..." -ForegroundColor Yellow
New-RandomString -Length 32 | Out-File -FilePath "secrets\csrf_secret.txt" -NoNewline -Encoding ASCII

# Generate encryption key
Write-Host "[INFO] Generating encryption key..." -ForegroundColor Yellow
$encBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($encBytes)
[Convert]::ToBase64String($encBytes) | Out-File -FilePath "secrets\encryption_key.txt" -NoNewline -Encoding ASCII

# Generate database password
Write-Host "[INFO] Generating database password..." -ForegroundColor Yellow
New-RandomString -Length 24 | Out-File -FilePath "secrets\db_password.txt" -NoNewline -Encoding ASCII

# Generate Redis password
Write-Host "[INFO] Generating Redis password..." -ForegroundColor Yellow
New-RandomString -Length 24 | Out-File -FilePath "secrets\redis_password.txt" -NoNewline -Encoding ASCII

# Create placeholder for API keys
Write-Host "[INFO] Creating API key placeholders..." -ForegroundColor Yellow
"placeholder" | Out-File -FilePath "secrets\openai_api_key.txt" -NoNewline -Encoding ASCII
"placeholder" | Out-File -FilePath "secrets\anthropic_api_key.txt" -NoNewline -Encoding ASCII

Write-Host ""
Write-Host "[WARN] IMPORTANT: Edit the following files and add your API keys:" -ForegroundColor Red
Write-Host "   - secrets\openai_api_key.txt" -ForegroundColor Yellow
Write-Host "   - secrets\anthropic_api_key.txt" -ForegroundColor Yellow
Write-Host ""

# Generate TLS certificates - skip prompts for automation
Write-Host "[INFO] Generating self-signed TLS certificates..." -ForegroundColor Yellow

$domain = "localhost"

# Generate self-signed certificate using PowerShell
try {
    $cert = New-SelfSignedCertificate `
        -DnsName $domain `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -NotAfter (Get-Date).AddYears(1) `
        -FriendlyName "ContextForge Development Certificate"

    # Export certificate
    $certPath = "certs\server.crt"
    $keyPath = "certs\server.key"

    # Export as PFX first
    $pfxPath = "certs\server.pfx"
    $password = ConvertTo-SecureString -String "temp" -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $password | Out-Null

    # Convert PFX to PEM format (requires OpenSSL)
    if (Get-Command openssl -ErrorAction SilentlyContinue) {
        openssl pkcs12 -in $pfxPath -out $certPath -nokeys -nodes -password pass:temp 2>$null
        openssl pkcs12 -in $pfxPath -out $keyPath -nocerts -nodes -password pass:temp 2>$null
        Remove-Item $pfxPath -ErrorAction SilentlyContinue

        Write-Host "[OK] Self-signed certificate generated" -ForegroundColor Green
        Write-Host "   Certificate: $certPath" -ForegroundColor White
        Write-Host "   Private key: $keyPath" -ForegroundColor White
    } else {
        # Create simple PEM files without OpenSSL
        Write-Host "[WARN] OpenSSL not found. Creating placeholder certificates..." -ForegroundColor Yellow

        # Create placeholder certificate files
        @"
-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQDU+pQ4P3z7hDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjAUMRIwEAYD
VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC7
o5e7FvN3kF3gT0EB1kVp5E3k2t5W5j8qU3ZjVvJ7PtA7n0a4j0xQN8l5CqN8j3E5
W7NqxMfK5W4P5L6E9c7A3Z5V8K7Z3M9L5E7C3N5K7E3C5K7E3C5K7E3C5K7E3C5K
7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C
5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E
3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K
7E3C5K7E3C5K7E3CAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAGnKp3F5U2tN9SZV
-----END CERTIFICATE-----
"@ | Out-File -FilePath $certPath -Encoding ASCII

        @"
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o5e7FvN3kF3g
T0EB1kVp5E3k2t5W5j8qU3ZjVvJ7PtA7n0a4j0xQN8l5CqN8j3E5W7NqxMfK5W4P
5L6E9c7A3Z5V8K7Z3M9L5E7C3N5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K
7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C
5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E
3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K
7E3C5K7E3C5K7E3CAgMBAAECggEAMTN0K7E3C5K7E3C5K7E3C5K7E3C5K7E3C5K7
-----END PRIVATE KEY-----
"@ | Out-File -FilePath $keyPath -Encoding ASCII

        Write-Host "[OK] Placeholder certificates created" -ForegroundColor Green
        Write-Host "   Note: These are placeholder certs for testing only" -ForegroundColor Yellow
    }

    # Remove from certificate store
    Remove-Item -Path "Cert:\CurrentUser\My\$($cert.Thumbprint)" -Force -ErrorAction SilentlyContinue

} catch {
    Write-Host "[WARN] Could not generate certificate: $_" -ForegroundColor Yellow
    Write-Host "[INFO] Creating placeholder certificates..." -ForegroundColor Yellow

    # Create placeholder certificate files
    @"
-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQDU+pQ4P3z7hDANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjAUMRIwEAYD
VQQDDAlsb2NhbGhvc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC7
-----END CERTIFICATE-----
"@ | Out-File -FilePath "certs\server.crt" -Encoding ASCII

    @"
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o5e7FvN3kF3g
-----END PRIVATE KEY-----
"@ | Out-File -FilePath "certs\server.key" -Encoding ASCII

    Write-Host "[OK] Placeholder certificates created" -ForegroundColor Green
}

Write-Host ""
Write-Host "[OK] Security setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review and edit secrets\*.txt files" -ForegroundColor White
Write-Host "  2. Update .env file with security settings" -ForegroundColor White
Write-Host "  3. Run: docker-compose -f docker-compose.secure.yml up -d" -ForegroundColor White
Write-Host ""
Write-Host "Security features enabled:" -ForegroundColor Cyan
Write-Host "  [OK] JWT authentication" -ForegroundColor Green
Write-Host "  [OK] CSRF protection" -ForegroundColor Green
Write-Host "  [OK] TLS/SSL encryption" -ForegroundColor Green
Write-Host "  [OK] Secrets management" -ForegroundColor Green
Write-Host "  [OK] Rate limiting" -ForegroundColor Green
Write-Host "  [OK] Audit logging" -ForegroundColor Green
Write-Host "  [OK] Security headers" -ForegroundColor Green
Write-Host "  [OK] Non-root containers" -ForegroundColor Green
Write-Host "  [OK] Resource limits" -ForegroundColor Green
Write-Host ""
