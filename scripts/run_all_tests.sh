#!/bin/bash
# Run all security tests for ContextForge
# This includes both integration tests and new feature-specific tests

set -e

echo "========================================="
echo "ContextForge Complete Test Suite"
echo "========================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing..."
    pip install pytest requests
fi

# Check if services are running
echo "Checking if ContextForge services are running..."
if ! curl -k -s https://localhost:8443/health > /dev/null 2>&1; then
    echo "WARNING: ContextForge API Gateway is not running"
    echo ""
    echo "Starting services..."
    docker-compose -f docker-compose.secure.yml up -d
    
    echo "Waiting for services to be ready..."
    sleep 10
    
    # Check again
    if ! curl -k -s https://localhost:8443/health > /dev/null 2>&1; then
        echo "ERROR: Services failed to start"
        echo ""
        echo "Please check logs:"
        echo "  docker-compose -f docker-compose.secure.yml logs"
        exit 1
    fi
fi

echo "✅ Services are running"
echo ""

# Create logs directory if it doesn't exist
mkdir -p ./logs

# Run all test suites
echo "========================================="
echo "Running Test Suites"
echo "========================================="
echo ""

# Test Suite 1: Integration Tests
echo "1. Running Integration Tests..."
echo "   - JWT Authentication"
echo "   - CSRF Protection"
echo "   - Rate Limiting"
echo "   - Security Headers"
echo "   - TLS Configuration"
echo "   - Audit Logging"
echo ""

pytest tests/security/test_integration.py -v --tb=short

INTEGRATION_EXIT_CODE=$?

echo ""
echo "========================================="
echo ""

# Test Suite 2: Cookie Authentication Tests
echo "2. Running Cookie Authentication Tests..."
echo "   - HTTP-only cookies"
echo "   - CSRF token handling"
echo "   - Token refresh flow"
echo "   - Logout functionality"
echo ""

pytest tests/security/test_cookie_auth.py -v --tb=short

COOKIE_EXIT_CODE=$?

echo ""
echo "========================================="
echo ""

# Test Suite 3: Terminal Sandbox Tests
echo "3. Running Terminal Sandbox Tests..."
echo "   - Sandbox configuration"
echo "   - Directory validation"
echo "   - Command whitelist"
echo "   - Audit logging"
echo ""

pytest tests/security/test_terminal_sandbox.py -v --tb=short

SANDBOX_EXIT_CODE=$?

echo ""
echo "========================================="
echo ""

# Test Suite 4: File Validation Tests
echo "4. Running File Validation Tests..."
echo "   - File type validation"
echo "   - File size limits"
echo "   - CSRF protection for uploads"
echo "   - Authentication requirements"
echo ""

pytest tests/security/test_file_validation.py -v --tb=short

FILE_EXIT_CODE=$?

echo ""
echo "========================================="
echo "Test Results Summary"
echo "========================================="
echo ""

# Calculate total results
TOTAL_TESTS=4
PASSED_TESTS=0

if [ $INTEGRATION_EXIT_CODE -eq 0 ]; then
    echo "✅ Integration Tests: PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ Integration Tests: FAILED"
fi

if [ $COOKIE_EXIT_CODE -eq 0 ]; then
    echo "✅ Cookie Authentication Tests: PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ Cookie Authentication Tests: FAILED"
fi

if [ $SANDBOX_EXIT_CODE -eq 0 ]; then
    echo "✅ Terminal Sandbox Tests: PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ Terminal Sandbox Tests: FAILED"
fi

if [ $FILE_EXIT_CODE -eq 0 ]; then
    echo "✅ File Validation Tests: PASSED"
    ((PASSED_TESTS++))
else
    echo "❌ File Validation Tests: FAILED"
fi

echo ""
echo "========================================="
echo "Overall: $PASSED_TESTS/$TOTAL_TESTS test suites passed"
echo "========================================="
echo ""

# Exit with failure if any test suite failed
if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo "🎉 All tests passed! Ready for deployment."
    exit 0
else
    echo "⚠️  Some tests failed. Please review the output above."
    exit 1
fi

