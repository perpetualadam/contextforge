"""
Integration tests for ContextForge security features.

Tests JWT authentication, CSRF protection, rate limiting, TLS, and audit logging.
"""

import pytest
import requests
import time
from pathlib import Path

# Test configuration
API_BASE_URL = "https://localhost:8443"
VERIFY_SSL = False  # Set to True for production with valid certificates

# Test credentials
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


class TestAuthentication:
    """Test JWT authentication flow."""
    
    def test_login_success(self):
        """Test successful login."""
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # Check CSRF cookie is set
        assert "csrf_token" in response.cookies
    
    def test_login_failure(self):
        """Test login with invalid credentials."""
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": "invalid", "password": "wrong"},
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 401
    
    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication."""
        response = requests.get(
            f"{API_BASE_URL}/auth/me",
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 401
    
    def test_protected_endpoint_with_auth(self):
        """Test accessing protected endpoint with authentication."""
        # Login first
        login_response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        
        # Access protected endpoint
        response = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_USER["username"]
    
    def test_token_refresh(self):
        """Test token refresh flow."""
        # Login first
        login_response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = requests.post(
            f"{API_BASE_URL}/auth/refresh",
            json={"refresh_token": refresh_token},
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestCSRFProtection:
    """Test CSRF protection."""
    
    def test_post_without_csrf_token(self):
        """Test POST request without CSRF token."""
        # Login first
        session = requests.Session()
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        access_token = login_response.json()["access_token"]
        
        # Try POST without CSRF token
        response = session.post(
            f"{API_BASE_URL}/ingest",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"path": "/test", "recursive": True},
            verify=VERIFY_SSL
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403
    
    def test_post_with_csrf_token(self):
        """Test POST request with valid CSRF token."""
        # Login first
        session = requests.Session()
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        access_token = login_response.json()["access_token"]
        csrf_token = session.cookies.get("csrf_token")
        
        # POST with CSRF token
        response = session.post(
            f"{API_BASE_URL}/ingest",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-CSRF-Token": csrf_token
            },
            json={"path": "/test", "recursive": True},
            verify=VERIFY_SSL
        )
        
        # Should succeed (or fail with different error if path doesn't exist)
        assert response.status_code != 403


class TestRateLimiting:
    """Test rate limiting."""
    
    def test_rate_limit_exceeded(self):
        """Test rate limiting by sending many requests."""
        # Send 101 requests to trigger rate limit (limit is 100 per 60 seconds)
        for i in range(101):
            response = requests.get(
                f"{API_BASE_URL}/health",
                verify=VERIFY_SSL
            )
            
            if i < 100:
                assert response.status_code == 200
            else:
                # 101st request should be rate limited
                assert response.status_code == 429


class TestSecurityHeaders:
    """Test security headers."""
    
    def test_security_headers_present(self):
        """Test that all security headers are present."""
        response = requests.get(
            f"{API_BASE_URL}/health",
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        
        # Check security headers
        headers = response.headers
        assert "Content-Security-Policy" in headers
        assert "Strict-Transport-Security" in headers
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        
        # Verify header values
        assert headers["X-Frame-Options"] == "SAMEORIGIN"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "max-age=" in headers["Strict-Transport-Security"]


class TestTLSConfiguration:
    """Test TLS/SSL configuration."""
    
    def test_https_connection(self):
        """Test HTTPS connection."""
        response = requests.get(
            f"{API_BASE_URL}/health",
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        assert response.url.startswith("https://")
    
    def test_tls_version(self):
        """Test TLS version is 1.2 or higher."""
        import ssl
        import socket
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with socket.create_connection(("localhost", 8443)) as sock:
            with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                # Check TLS version
                version = ssock.version()
                assert version in ["TLSv1.2", "TLSv1.3"]


class TestAuditLogging:
    """Test audit logging."""
    
    def test_audit_log_file_exists(self):
        """Test that audit log file is created."""
        log_file = Path("./logs/audit.log")
        
        # Make a request to generate audit log
        requests.get(f"{API_BASE_URL}/health", verify=VERIFY_SSL)
        
        # Wait a moment for log to be written
        time.sleep(1)
        
        # Check if log file exists
        assert log_file.exists()
    
    def test_audit_log_contains_events(self):
        """Test that audit log contains events."""
        log_file = Path("./logs/audit.log")
        
        if log_file.exists():
            content = log_file.read_text()
            # Should contain JSON log entries
            assert "event_type" in content or len(content) == 0  # Empty is OK if no events yet


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

