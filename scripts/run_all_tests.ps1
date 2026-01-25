# Run all security tests for ContextForge (Windows)
# This includes both integration tests and new feature-specific tests

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ContextForge Complete Test Suite" -ForegroundColor Cyan
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
    Write-Host "WARNING: ContextForge API Gateway is not running" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Starting services..." -ForegroundColor Yellow
    docker-compose -f docker-compose.secure.yml up -d
    
    Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    # Check again
    try {
        $response = Invoke-WebRequest -Uri "https://localhost:8443/health" -SkipCertificateCheck -ErrorAction Stop
        Write-Host "✅ Services are now running" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Services failed to start" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please check logs:" -ForegroundColor Yellow
        Write-Host "  docker-compose -f docker-compose.secure.yml logs" -ForegroundColor White
        exit 1
    }
}

Write-Host ""

# Create logs directory if it doesn't exist
if (-not (Test-Path "./logs")) {
    New-Item -ItemType Directory -Path "./logs" | Out-Null
}

# Run all test suites
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Running Test Suites" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Test Suite 1: Integration Tests
Write-Host "1. Running Integration Tests..." -ForegroundColor Yellow
Write-Host "   - JWT Authentication" -ForegroundColor White
Write-Host "   - CSRF Protection" -ForegroundColor White
Write-Host "   - Rate Limiting" -ForegroundColor White
Write-Host "   - Security Headers" -ForegroundColor White
Write-Host "   - TLS Configuration" -ForegroundColor White
Write-Host "   - Audit Logging" -ForegroundColor White
Write-Host ""

pytest tests/security/test_integration.py -v --tb=short
$IntegrationExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Test Suite 2: Cookie Authentication Tests
Write-Host "2. Running Cookie Authentication Tests..." -ForegroundColor Yellow
Write-Host "   - HTTP-only cookies" -ForegroundColor White
Write-Host "   - CSRF token handling" -ForegroundColor White
Write-Host "   - Token refresh flow" -ForegroundColor White
Write-Host "   - Logout functionality" -ForegroundColor White
Write-Host ""

pytest tests/security/test_cookie_auth.py -v --tb=short
$CookieExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Test Suite 3: Terminal Sandbox Tests
Write-Host "3. Running Terminal Sandbox Tests..." -ForegroundColor Yellow
Write-Host "   - Sandbox configuration" -ForegroundColor White
Write-Host "   - Directory validation" -ForegroundColor White
Write-Host "   - Command whitelist" -ForegroundColor White
Write-Host "   - Audit logging" -ForegroundColor White
Write-Host ""

pytest tests/security/test_terminal_sandbox.py -v --tb=short
$SandboxExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Test Suite 4: File Validation Tests
Write-Host "4. Running File Validation Tests..." -ForegroundColor Yellow
Write-Host "   - File type validation" -ForegroundColor White
Write-Host "   - File size limits" -ForegroundColor White
Write-Host "   - CSRF protection for uploads" -ForegroundColor White
Write-Host "   - Authentication requirements" -ForegroundColor White
Write-Host ""

pytest tests/security/test_file_validation.py -v --tb=short
$FileExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Test Results Summary" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Calculate total results
$TotalTests = 4
$PassedTests = 0

if ($IntegrationExitCode -eq 0) {
    Write-Host "✅ Integration Tests: PASSED" -ForegroundColor Green
    $PassedTests++
} else {
    Write-Host "❌ Integration Tests: FAILED" -ForegroundColor Red
}

if ($CookieExitCode -eq 0) {
    Write-Host "✅ Cookie Authentication Tests: PASSED" -ForegroundColor Green
    $PassedTests++
} else {
    Write-Host "❌ Cookie Authentication Tests: FAILED" -ForegroundColor Red
}

if ($SandboxExitCode -eq 0) {
    Write-Host "✅ Terminal Sandbox Tests: PASSED" -ForegroundColor Green
    $PassedTests++
} else {
    Write-Host "❌ Terminal Sandbox Tests: FAILED" -ForegroundColor Red
}

if ($FileExitCode -eq 0) {
    Write-Host "✅ File Validation Tests: PASSED" -ForegroundColor Green
    $PassedTests++
} else {
    Write-Host "❌ File Validation Tests: FAILED" -ForegroundColor Red
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Overall: $PassedTests/$TotalTests test suites passed" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Exit with failure if any test suite failed
if ($PassedTests -eq $TotalTests) {
    Write-Host "🎉 All tests passed! Ready for deployment." -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠️  Some tests failed. Please review the output above." -ForegroundColor Yellow
    exit 1
}

