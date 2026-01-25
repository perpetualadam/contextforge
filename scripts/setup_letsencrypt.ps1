# Setup Let's Encrypt certificates for ContextForge production deployment (Windows)
# This script uses win-acme to obtain and configure SSL certificates

param(
    [Parameter(Mandatory=$false)]
    [string]$Domain,
    
    [Parameter(Mandatory=$false)]
    [string]$Email
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ContextForge Let's Encrypt Setup (Windows)" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Get domain name if not provided
if (-not $Domain) {
    $Domain = Read-Host "Enter your domain name (e.g., contextforge.example.com)"
    if (-not $Domain) {
        Write-Host "ERROR: Domain name is required" -ForegroundColor Red
        exit 1
    }
}

# Get email if not provided
if (-not $Email) {
    $Email = Read-Host "Enter your email address for Let's Encrypt notifications"
    if (-not $Email) {
        Write-Host "ERROR: Email address is required" -ForegroundColor Red
        exit 1
    }
}

# Create certs directory
$CertsDir = Join-Path $PSScriptRoot "..\certs"
if (-not (Test-Path $CertsDir)) {
    New-Item -ItemType Directory -Path $CertsDir | Out-Null
}

Write-Host ""
Write-Host "Windows Let's Encrypt Setup Options:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Option 1: Use win-acme (Recommended for Windows)" -ForegroundColor Green
Write-Host "  - Download from: https://www.win-acme.com/"
Write-Host "  - Automated certificate management"
Write-Host "  - Automatic renewal"
Write-Host ""
Write-Host "Option 2: Use Certify The Web (GUI)" -ForegroundColor Green
Write-Host "  - Download from: https://certifytheweb.com/"
Write-Host "  - User-friendly GUI"
Write-Host "  - Free for up to 5 certificates"
Write-Host ""
Write-Host "Option 3: Manual Certificate (For Testing)" -ForegroundColor Yellow
Write-Host "  - Use self-signed certificate"
Write-Host "  - Not recommended for production"
Write-Host ""

$choice = Read-Host "Select option (1, 2, or 3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Installing win-acme..." -ForegroundColor Cyan
        
        # Download win-acme
        $winAcmeUrl = "https://github.com/win-acme/win-acme/releases/latest/download/win-acme.v2.2.7.1612.x64.pluggable.zip"
        $winAcmeZip = Join-Path $env:TEMP "win-acme.zip"
        $winAcmeDir = Join-Path $env:ProgramFiles "win-acme"
        
        try {
            Write-Host "Downloading win-acme..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $winAcmeUrl -OutFile $winAcmeZip -UseBasicParsing
            
            Write-Host "Extracting win-acme..." -ForegroundColor Yellow
            Expand-Archive -Path $winAcmeZip -DestinationPath $winAcmeDir -Force
            
            Write-Host ""
            Write-Host "✅ win-acme installed to: $winAcmeDir" -ForegroundColor Green
            Write-Host ""
            Write-Host "To obtain certificate, run:" -ForegroundColor Yellow
            Write-Host "  cd `"$winAcmeDir`"" -ForegroundColor White
            Write-Host "  .\wacs.exe --target manual --host $Domain --emailaddress $Email" -ForegroundColor White
            Write-Host ""
            Write-Host "After obtaining the certificate:" -ForegroundColor Yellow
            Write-Host "1. Copy the certificate files to: $CertsDir" -ForegroundColor White
            Write-Host "2. Rename fullchain.pem to server.crt" -ForegroundColor White
            Write-Host "3. Rename privkey.pem to server.key" -ForegroundColor White
            
        } catch {
            Write-Host "ERROR: Failed to download win-acme: $_" -ForegroundColor Red
            Write-Host "Please download manually from: https://www.win-acme.com/" -ForegroundColor Yellow
        }
    }
    
    "2" {
        Write-Host ""
        Write-Host "Opening Certify The Web download page..." -ForegroundColor Cyan
        Start-Process "https://certifytheweb.com/home/download"
        
        Write-Host ""
        Write-Host "After installing Certify The Web:" -ForegroundColor Yellow
        Write-Host "1. Launch Certify The Web" -ForegroundColor White
        Write-Host "2. Click 'New Certificate'" -ForegroundColor White
        Write-Host "3. Enter domain: $Domain" -ForegroundColor White
        Write-Host "4. Enter email: $Email" -ForegroundColor White
        Write-Host "5. Follow the wizard to obtain certificate" -ForegroundColor White
        Write-Host "6. Export certificate to: $CertsDir" -ForegroundColor White
    }
    
    "3" {
        Write-Host ""
        Write-Host "Using self-signed certificate (for testing only)..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Run the following command to generate self-signed certificate:" -ForegroundColor Yellow
        Write-Host "  .\scripts\setup_security.ps1" -ForegroundColor White
        Write-Host ""
        Write-Host "WARNING: Self-signed certificates are not trusted by browsers" -ForegroundColor Red
        Write-Host "Use Let's Encrypt for production deployments" -ForegroundColor Red
    }
    
    default {
        Write-Host "Invalid option selected" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Additional Configuration" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Update .env file
$envFile = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    
    if ($envContent -match "^TLS_ENABLED=") {
        $envContent = $envContent -replace "^TLS_ENABLED=.*", "TLS_ENABLED=true"
    } else {
        $envContent += "`nTLS_ENABLED=true"
    }
    
    Set-Content -Path $envFile -Value $envContent
    Write-Host "✅ Updated .env file with TLS_ENABLED=true" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Update your DNS to point $Domain to this server" -ForegroundColor White
Write-Host "2. Ensure ports 80 and 443 are open in your firewall" -ForegroundColor White
Write-Host "3. Obtain SSL certificate using chosen method" -ForegroundColor White
Write-Host "4. Copy certificate files to: $CertsDir" -ForegroundColor White
Write-Host "5. Deploy ContextForge with: docker-compose -f docker-compose.secure.yml up -d" -ForegroundColor White
Write-Host "6. Access ContextForge at: https://${Domain}:8443" -ForegroundColor White
Write-Host ""

