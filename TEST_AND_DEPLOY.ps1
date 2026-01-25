# ContextForge - Automated Test and Deploy Script
param(
    [switch]$SkipTests = $false,
    [switch]$SkipDeploy = $false
)

$ErrorActionPreference = "Continue"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ContextForge - Test and Deploy" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Docker is running
Write-Host "Step 1: Checking Docker..." -ForegroundColor Yellow
$dockerCheck = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Docker is running" -ForegroundColor Green
Write-Host ""

# Step 2: Check if pytest is installed
Write-Host "Step 2: Checking pytest..." -ForegroundColor Yellow
$pytestCheck = pytest --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] pytest not found. Installing..." -ForegroundColor Yellow
    pip install pytest requests
}
Write-Host "[OK] pytest is installed" -ForegroundColor Green
Write-Host ""

# Step 3: Start services
Write-Host "Step 3: Starting services..." -ForegroundColor Yellow
$running = docker-compose -f docker-compose.secure.yml ps --services --filter "status=running" 2>&1

if ($running -and $running.Length -gt 0) {
    Write-Host "[OK] Services are already running" -ForegroundColor Green
} else {
    Write-Host "Starting Docker Compose services..." -ForegroundColor Yellow
    docker-compose -f docker-compose.secure.yml up -d
    Write-Host "Waiting 30 seconds for services to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
}
Write-Host ""

# Step 4: Verify services are healthy
Write-Host "Step 4: Verifying services..." -ForegroundColor Yellow
$maxRetries = 5
$retryCount = 0
$healthy = $false

while ($retryCount -lt $maxRetries -and -not $healthy) {
    try {
        $response = Invoke-WebRequest -Uri "https://localhost:8443/health" -SkipCertificateCheck -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            Write-Host "[OK] API Gateway is healthy" -ForegroundColor Green
        }
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "[WAIT] Waiting for services... (attempt $retryCount of $maxRetries)" -ForegroundColor Yellow
            Start-Sleep -Seconds 10
        }
    }
}

if (-not $healthy) {
    Write-Host "[FAIL] Services failed to start properly" -ForegroundColor Red
    Write-Host "Check logs with: docker-compose -f docker-compose.secure.yml logs" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Step 5: Run tests
if (-not $SkipTests) {
    Write-Host "Step 5: Running tests..." -ForegroundColor Yellow
    Write-Host ""

    pytest tests/security/ -v --tb=short
    $testExitCode = $LASTEXITCODE

    Write-Host ""

    if ($testExitCode -eq 0) {
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "[OK] All tests passed!" -ForegroundColor Green
        Write-Host "=========================================" -ForegroundColor Green
    } else {
        Write-Host "=========================================" -ForegroundColor Red
        Write-Host "[FAIL] Some tests failed" -ForegroundColor Red
        Write-Host "=========================================" -ForegroundColor Red
        Write-Host "Please fix the failing tests before deploying." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "Step 5: Skipping tests (--SkipTests flag)" -ForegroundColor Yellow
}
Write-Host ""

# Step 6: Deploy to GitHub
if (-not $SkipDeploy) {
    Write-Host "Step 6: Deploying to GitHub..." -ForegroundColor Yellow
    Write-Host ""

    $status = git status --porcelain

    if ($status) {
        Write-Host "[INFO] Uncommitted changes detected" -ForegroundColor Yellow
        git add .

        $commitMsg = "feat: Complete security hardening with optional enhancements"
        git commit -m $commitMsg
        Write-Host "[OK] Changes committed" -ForegroundColor Green
    } else {
        Write-Host "[OK] No uncommitted changes" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Pushing to GitHub..." -ForegroundColor Yellow

    $currentBranch = git branch --show-current
    git push origin $currentBranch

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "[OK] Successfully deployed to GitHub!" -ForegroundColor Green
        Write-Host "=========================================" -ForegroundColor Green
        Write-Host "Branch: $currentBranch" -ForegroundColor Cyan
        Write-Host "Repository: https://github.com/perpetualadam/contextforge" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "=========================================" -ForegroundColor Red
        Write-Host "[FAIL] Push failed" -ForegroundColor Red
        Write-Host "=========================================" -ForegroundColor Red
        Write-Host "You may need to configure GitHub authentication." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "Step 6: Skipping deployment (--SkipDeploy flag)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[DONE] All done!" -ForegroundColor Green
Write-Host ""
