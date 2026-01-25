#!/bin/bash
# Deploy ContextForge security enhancements to GitHub

set -e

echo "========================================="
echo "ContextForge GitHub Deployment"
echo "========================================="
echo ""

# Check if we're in a git repository
if [ ! -d .git ]; then
    echo "ERROR: Not a git repository"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "📝 Uncommitted changes detected"
    echo ""
    
    # Show status
    git status --short
    echo ""
    
    read -p "Do you want to commit these changes? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Add all changes
        echo "Adding all changes..."
        git add .
        
        # Show what will be committed
        echo ""
        echo "Files to be committed:"
        git diff --cached --name-status
        echo ""
        
        # Get commit message
        echo "Enter commit message (or press Enter for default):"
        read -r COMMIT_MSG
        
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="feat: Complete security hardening with optional enhancements

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
- File upload validation tests"
        fi
        
        # Commit changes
        echo ""
        echo "Committing changes..."
        git commit -m "$COMMIT_MSG"
        
        echo "✅ Changes committed"
    else
        echo "Deployment cancelled"
        exit 1
    fi
else
    echo "✅ No uncommitted changes"
fi

echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""

# Check if remote exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "ERROR: No remote 'origin' configured"
    echo ""
    echo "Please add a remote:"
    echo "  git remote add origin https://github.com/perpetualadam/contextforge.git"
    exit 1
fi

REMOTE_URL=$(git remote get-url origin)
echo "Remote URL: $REMOTE_URL"
echo ""

# Ask for confirmation
read -p "Push to $CURRENT_BRANCH on $REMOTE_URL? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
fi

# Push to GitHub
echo ""
echo "Pushing to GitHub..."
git push origin $CURRENT_BRANCH

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ Successfully deployed to GitHub!"
    echo "========================================="
    echo ""
    echo "Branch: $CURRENT_BRANCH"
    echo "Remote: $REMOTE_URL"
    echo ""
    echo "Next steps:"
    echo "1. Visit: https://github.com/perpetualadam/contextforge"
    echo "2. Create a Pull Request (if using feature branch)"
    echo "3. Review changes and merge"
    echo ""
else
    echo ""
    echo "========================================="
    echo "❌ Push failed"
    echo "========================================="
    echo ""
    echo "Common issues:"
    echo "1. Authentication required - configure GitHub credentials"
    echo "2. Branch protection - create a PR instead"
    echo "3. Network issues - check internet connection"
    echo ""
    exit 1
fi

