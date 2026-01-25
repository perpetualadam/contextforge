"""
Unit tests for frontend file validation.

Tests file type validation, file size limits, and CSRF protection for uploads.
"""

import pytest
import requests
import io
from pathlib import Path

# Test configuration
API_BASE_URL = "https://localhost:8443"
VERIFY_SSL = False

TEST_USER = {
    "username": "admin",
    "password": "admin123"
}


class TestFileValidation:
    """Test file upload validation and security."""
    
    @pytest.fixture
    def authenticated_session(self):
        """Create an authenticated session for testing."""
        session = requests.Session()
        
        # Login
        login_response = session.post(
            f"{API_BASE_URL}/auth/login",
            json=TEST_USER,
            verify=VERIFY_SSL
        )
        
        assert login_response.status_code == 200
        
        session.access_token = login_response.json()["access_token"]
        session.csrf_token = session.cookies.get("csrf_token")
        
        return session
    
    def test_upload_allowed_file_type_jpeg(self, authenticated_session):
        """Test uploading allowed file type (JPEG)."""
        # Create a small JPEG-like file
        file_content = b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG header
        file = io.BytesIO(file_content)
        
        response = authenticated_session.post(
            f"{API_BASE_URL}/files/upload",
            headers={
                "Authorization": f"Bearer {authenticated_session.access_token}",
                "X-CSRF-Token": authenticated_session.csrf_token
            },
            files={"file": ("test.jpg", file, "image/jpeg")},
            verify=VERIFY_SSL
        )
        
        # Should succeed or fail with validation error (not 403 Forbidden)
        assert response.status_code != 403
    
    def test_upload_allowed_file_type_pdf(self, authenticated_session):
        """Test uploading allowed file type (PDF)."""
        # Create a small PDF-like file
        file_content = b'%PDF-1.4'
        file = io.BytesIO(file_content)
        
        response = authenticated_session.post(
            f"{API_BASE_URL}/files/upload",
            headers={
                "Authorization": f"Bearer {authenticated_session.access_token}",
                "X-CSRF-Token": authenticated_session.csrf_token
            },
            files={"file": ("test.pdf", file, "application/pdf")},
            verify=VERIFY_SSL
        )
        
        # Should succeed or fail with validation error (not 403 Forbidden)
        assert response.status_code != 403
    
    def test_upload_text_file(self, authenticated_session):
        """Test uploading text file."""
        file_content = b'This is a test file.'
        file = io.BytesIO(file_content)
        
        response = authenticated_session.post(
            f"{API_BASE_URL}/files/upload",
            headers={
                "Authorization": f"Bearer {authenticated_session.access_token}",
                "X-CSRF-Token": authenticated_session.csrf_token
            },
            files={"file": ("test.txt", file, "text/plain")},
            verify=VERIFY_SSL
        )
        
        # Should succeed or fail with validation error (not 403 Forbidden)
        assert response.status_code != 403
    
    def test_upload_without_csrf_token(self, authenticated_session):
        """Test that file upload requires CSRF token."""
        file_content = b'Test content'
        file = io.BytesIO(file_content)
        
        # Upload without CSRF token
        response = authenticated_session.post(
            f"{API_BASE_URL}/files/upload",
            headers={
                "Authorization": f"Bearer {authenticated_session.access_token}"
                # No X-CSRF-Token header
            },
            files={"file": ("test.txt", file, "text/plain")},
            verify=VERIFY_SSL
        )
        
        # Should be forbidden without CSRF token
        assert response.status_code == 403
    
    def test_upload_without_authentication(self):
        """Test that file upload requires authentication."""
        file_content = b'Test content'
        file = io.BytesIO(file_content)
        
        response = requests.post(
            f"{API_BASE_URL}/files/upload",
            files={"file": ("test.txt", file, "text/plain")},
            verify=VERIFY_SSL
        )
        
        # Should be unauthorized without authentication
        assert response.status_code == 401
    
    def test_file_size_validation_client_side(self):
        """Test that client-side file size validation is implemented.
        
        Note: This test verifies the implementation exists in the code.
        Actual validation happens in the browser/frontend.
        """
        # This is a code review test - verify the implementation exists
        client_code_path = Path("web-frontend/src/api/client.ts")
        
        if client_code_path.exists():
            with open(client_code_path, 'r') as f:
                content = f.read()
            
            # Check for file size validation
            assert "maxSize" in content or "max_size" in content
            assert "50 * 1024 * 1024" in content or "52428800" in content  # 50 MB
            
            # Check for file type validation
            assert "allowedTypes" in content or "allowed_types" in content
            assert "image/jpeg" in content
            assert "application/pdf" in content
        else:
            pytest.skip("Frontend code not available for inspection")
    
    def test_file_type_validation_client_side(self):
        """Test that client-side file type validation is implemented.
        
        Note: This test verifies the implementation exists in the code.
        """
        client_code_path = Path("web-frontend/src/api/client.ts")
        
        if client_code_path.exists():
            with open(client_code_path, 'r') as f:
                content = f.read()
            
            # Check for allowed file types
            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/gif",
                "application/pdf",
                "text/plain",
                "text/markdown"
            ]
            
            for file_type in allowed_types:
                assert file_type in content
        else:
            pytest.skip("Frontend code not available for inspection")
    
    def test_csrf_token_in_upload_request(self):
        """Test that CSRF token is included in upload requests.
        
        Note: This test verifies the implementation exists in the code.
        """
        client_code_path = Path("web-frontend/src/api/client.ts")
        
        if client_code_path.exists():
            with open(client_code_path, 'r') as f:
                content = f.read()
            
            # Check for CSRF token in upload function
            assert "X-CSRF-Token" in content
            assert "csrfToken" in content
            
            # Check for credentials: 'include'
            assert "credentials" in content
            assert "'include'" in content or '"include"' in content
        else:
            pytest.skip("Frontend code not available for inspection")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

