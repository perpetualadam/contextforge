# Deploy ContextForge security enhancements to GitHub (Windows)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "ContextForge GitHub Deployment" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repository
if (-not (Test-Path .git)) {
    Write-Host "ERROR: Not a git repository" -ForegroundColor Red
    exit 1
}

# Check for uncommitted changes
$status = git status --porcelain

if ($status) {
    Write-Host "📝 Uncommitted changes detected" -ForegroundColor Yellow
    Write-Host ""
    
    # Show status
    git status --short
    Write-Host ""
    
    $commit = Read-Host "Do you want to commit these changes? (y/n)"
    
    if ($commit -eq 'y' -or $commit -eq 'Y') {
        # Add all changes
        Write-Host "Adding all changes..." -ForegroundColor Yellow
        git add .
        
        # Show what will be committed
        Write-Host ""
        Write-Host "Files to be committed:" -ForegroundColor Yellow
        git diff --cached --name-status
        Write-Host ""
        
        # Get commit message
        Write-Host "Enter commit message (or press Enter for default):" -ForegroundColor Yellow
        $commitMsg = Read-Host
        
        if ([string]::IsNullOrWhiteSpace($commitMsg)) {
            $commitMsg = @"
feat: Complete security hardening with optional enhancements

- Implemented HTTP-only cookie authentication (removed localStorage)
- Added terminal executor sandbox validation and command whitelist
- Implemented frontend file type/size validation with CSRF protection
- Added Let's Encrypt integration for production TLS certificates
- Created comprehensive integration test suite
- Added deployment documentation and guides

Security Features:
- JWT authentication with RBAC
- CSRF protection for all state-changing requests
- Distributed rate limiting with Redis
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Audit logging for all security events
- Container security (non-root, resource limits)
- TLS/SSL with automatic certificate renewal

Tests:
- Integration tests for all security features
- Cookie authentication tests
- Terminal sandbox validation tests
- File upload validation tests
"@
        }
        
        # Commit changes
        Write-Host ""
        Write-Host "Committing changes..." -ForegroundColor Yellow
        git commit -m $commitMsg
        
        Write-Host "✅ Changes committed" -ForegroundColor Green
    } else {
        Write-Host "Deployment cancelled" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "✅ No uncommitted changes" -ForegroundColor Green
}

Write-Host ""

# Check current branch
$currentBranch = git branch --show-current
Write-Host "Current branch: $currentBranch" -ForegroundColor Cyan
Write-Host ""

# Check if remote exists
try {
    $remoteUrl = git remote get-url origin
    Write-Host "Remote URL: $remoteUrl" -ForegroundColor Cyan
} catch {
    Write-Host "ERROR: No remote 'origin' configured" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please add a remote:" -ForegroundColor Yellow
    Write-Host "  git remote add origin https://github.com/perpetualadam/contextforge.git" -ForegroundColor White
    exit 1
}

Write-Host ""

# Ask for confirmation
$push = Read-Host "Push to $currentBranch on $remoteUrl? (y/n)"

if ($push -ne 'y' -and $push -ne 'Y') {
    Write-Host "Deployment cancelled" -ForegroundColor Yellow
    exit 1
}

# Push to GitHub
Write-Host ""
Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
git push origin $currentBranch

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host "✅ Successfully deployed to GitHub!" -ForegroundColor Green
    Write-Host "=========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Branch: $currentBranch" -ForegroundColor Cyan
    Write-Host "Remote: $remoteUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Visit: https://github.com/perpetualadam/contextforge" -ForegroundColor White
    Write-Host "2. Create a Pull Request (if using feature branch)" -ForegroundColor White
    Write-Host "3. Review changes and merge" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host "❌ Push failed" -ForegroundColor Red
    Write-Host "=========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "1. Authentication required - configure GitHub credentials" -ForegroundColor White
    Write-Host "2. Branch protection - create a PR instead" -ForegroundColor White
    Write-Host "3. Network issues - check internet connection" -ForegroundColor White
    Write-Host ""
    exit 1
}

