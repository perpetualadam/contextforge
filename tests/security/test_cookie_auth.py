"""
Unit tests for HTTP-only cookie authentication.

Tests the implementation of cookie-based authentication replacing localStorage.
"""

import pytest
import requests
from unittest.mock import Mock, patch

# Test configuration
API_BASE_URL = "https://localhost:8443"
VERIFY_SSL = False

TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


class TestCookieAuthentication:
    """Test HTTP-only cookie authentication implementation."""
    
    def test_login_sets_csrf_cookie(self):
        """Test that login sets CSRF token in cookies."""
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        
        # Check CSRF cookie is set
        assert "csrf_token" in response.cookies
        csrf_token = response.cookies.get("csrf_token")
        assert csrf_token is not None
        assert len(csrf_token) > 0
    
    def test_login_returns_tokens(self):
        """Test that login returns access and refresh tokens."""
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check tokens are returned
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        
        # Tokens should be non-empty strings
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
        assert isinstance(data["refresh_token"], str)
        assert len(data["refresh_token"]) > 0
    
    def test_csrf_cookie_attributes(self):
        """Test that CSRF cookie has proper security attributes."""
        session = requests.Session()
        response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        
        # Get CSRF cookie
        csrf_cookie = session.cookies.get("csrf_token")
        assert csrf_cookie is not None
        
        # Note: requests library doesn't expose all cookie attributes
        # In production, verify these in browser DevTools:
        # - HttpOnly: true
        # - Secure: true (in production)
        # - SameSite: Lax or Strict
    
    def test_authenticated_request_with_cookies(self):
        """Test making authenticated requests using cookies."""
        session = requests.Session()
        
        # Login to get tokens and cookies
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        
        # Make authenticated request
        response = session.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            verify=VERIFY_SSL
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == TEST_USER["username"]
    
    def test_csrf_protection_on_post(self):
        """Test that POST requests require CSRF token."""
        session = requests.Session()
        
        # Login first
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        access_token = login_response.json()["access_token"]
        csrf_token = session.cookies.get("csrf_token")
        
        # POST without CSRF token should fail
        response_without_csrf = session.post(
            f"{API_BASE_URL}/ingest",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"path": "/test", "recursive": True},
            verify=VERIFY_SSL
        )
        
        # Should be forbidden without CSRF token
        assert response_without_csrf.status_code == 403
        
        # POST with CSRF token should succeed (or fail with different error)
        response_with_csrf = session.post(
            f"{API_BASE_URL}/ingest",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-CSRF-Token": csrf_token
            },
            json={"path": "/test", "recursive": True},
            verify=VERIFY_SSL
        )
        
        # Should not be forbidden (may fail with 404 or other error if path doesn't exist)
        assert response_with_csrf.status_code != 403
    
    def test_logout_clears_session(self):
        """Test that logout clears the session."""
        session = requests.Session()
        
        # Login
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        access_token = login_response.json()["access_token"]
        
        # Logout
        logout_response = session.post(
            f"{API_BASE_URL}/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            verify=VERIFY_SSL
        )
        
        assert logout_response.status_code == 200
        
        # Try to access protected endpoint with old token
        response = session.get(
            f"{API_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            verify=VERIFY_SSL
        )
        
        # Should be unauthorized after logout
        assert response.status_code == 401
    
    def test_token_refresh_flow(self):
        """Test token refresh using refresh token."""
        # Login
        login_response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        refresh_response = requests.post(
            f"{API_BASE_URL}/auth/refresh",
            json={"refresh_token": refresh_token},
            verify=VERIFY_SSL
        )
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        
        # Should get new tokens
        assert "access_token" in data
        assert "refresh_token" in data
        
        # New tokens should be different from old ones
        assert data["access_token"] != login_response.json()["access_token"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

