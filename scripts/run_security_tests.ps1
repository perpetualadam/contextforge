# Run security integration tests for ContextForge (Windows)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ContextForge Security Integration Tests" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if pytest is installed
try {
    pytest --version | Out-Null
} catch {
    Write-Host "pytest not found. Installing..." -ForegroundColor Yellow
    pip install pytest requests
}

# Check if services are running
Write-Host "Checking if ContextForge services are running..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "https://localhost:8443/health" -SkipCertificateCheck -ErrorAction Stop
    Write-Host "✅ Services are running" -ForegroundColor Green
} catch {
    Write-Host "ERROR: ContextForge API Gateway is not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the services first:" -ForegroundColor Yellow
    Write-Host "  docker-compose -f docker-compose.secure.yml up -d" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host ""

# Create logs directory if it doesn't exist
if (-not (Test-Path "./logs")) {
    New-Item -ItemType Directory -Path "./logs" | Out-Null
}

# Run tests
Write-Host "Running security integration tests..." -ForegroundColor Yellow
Write-Host ""

pytest tests/security/test_integration.py -v --tb=short

$TestExitCode = $LASTEXITCODE

Write-Host ""
if ($TestExitCode -eq 0) {
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "✅ All security tests passed!" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
} else {
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host "❌ Some security tests failed" -ForegroundColor Red
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the output above for details" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Test Summary:" -ForegroundColor Cyan
Write-Host "- JWT Authentication: Tested" -ForegroundColor White
Write-Host "- CSRF Protection: Tested" -ForegroundColor White
Write-Host "- Rate Limiting: Tested" -ForegroundColor White
Write-Host "- Security Headers: Tested" -ForegroundColor White
Write-Host "- TLS Configuration: Tested" -ForegroundColor White
Write-Host "- Audit Logging: Tested" -ForegroundColor White
Write-Host ""

exit $TestExitCode

