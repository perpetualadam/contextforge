#!/bin/bash
# Run security integration tests for ContextForge

set -e

echo "========================================="
echo "ContextForge Security Integration Tests"
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
    echo "ERROR: ContextForge API Gateway is not running"
    echo ""
    echo "Please start the services first:"
    echo "  docker-compose -f docker-compose.secure.yml up -d"
    echo ""
    exit 1
fi

echo "✅ Services are running"
echo ""

# Create logs directory if it doesn't exist
mkdir -p ./logs

# Run tests
echo "Running security integration tests..."
echo ""

pytest tests/security/test_integration.py -v --tb=short

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "========================================="
    echo "✅ All security tests passed!"
    echo "========================================="
else
    echo "========================================="
    echo "❌ Some security tests failed"
    echo "========================================="
    echo ""
    echo "Check the output above for details"
fi

echo ""
echo "Test Summary:"
echo "- JWT Authentication: Tested"
echo "- CSRF Protection: Tested"
echo "- Rate Limiting: Tested"
echo "- Security Headers: Tested"
echo "- TLS Configuration: Tested"
echo "- Audit Logging: Tested"
echo ""

exit $TEST_EXIT_CODE

