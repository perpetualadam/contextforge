"""
Tests for ContextForge Browser Opener tool.

Copyright (c) 2025 ContextForge
"""

import pytest
from unittest.mock import patch, MagicMock

from services.tools.browser_opener import (
    BrowserOpener,
    BrowserOpenRequest,
    BrowserOpenResult,
    BrowserOpenStatus,
    get_browser_opener,
    reset_browser_opener
)


@pytest.fixture
def opener():
    """Create a BrowserOpener instance."""
    return BrowserOpener(track_duplicates=True)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    reset_browser_opener()
    yield
    reset_browser_opener()


class TestURLValidation:
    """Tests for URL validation."""
    
    def test_valid_http_url(self, opener):
        """Test valid HTTP URL passes validation."""
        is_valid, error = opener._validate_url("http://example.com")
        assert is_valid is True
        assert error == ""
    
    def test_valid_https_url(self, opener):
        """Test valid HTTPS URL passes validation."""
        is_valid, error = opener._validate_url("https://example.com/path?query=1")
        assert is_valid is True
        assert error == ""
    
    def test_empty_url(self, opener):
        """Test empty URL fails validation."""
        is_valid, error = opener._validate_url("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_invalid_scheme(self, opener):
        """Test non-http/https schemes fail."""
        is_valid, error = opener._validate_url("ftp://example.com")
        assert is_valid is False
        assert "scheme" in error.lower()
    
    def test_file_scheme_blocked(self, opener):
        """Test file:// scheme is blocked."""
        is_valid, error = opener._validate_url("file:///etc/passwd")
        assert is_valid is False
    
    def test_javascript_scheme_blocked(self, opener):
        """Test javascript: scheme is blocked."""
        is_valid, error = opener._validate_url("javascript:alert(1)")
        assert is_valid is False
    
    def test_missing_domain(self, opener):
        """Test URL without domain fails."""
        is_valid, error = opener._validate_url("http://")
        assert is_valid is False
        assert "domain" in error.lower()


class TestBrowserOpening:
    """Tests for browser opening functionality."""
    
    @patch('webbrowser.open')
    def test_successful_open(self, mock_open, opener):
        """Test successful URL opening."""
        mock_open.return_value = True
        
        request = BrowserOpenRequest(url="https://example.com")
        result = opener.open(request)
        
        assert result.status == BrowserOpenStatus.SUCCESS
        assert result.url == "https://example.com"
        mock_open.assert_called_once()
    
    @patch('webbrowser.open')
    def test_open_in_new_tab(self, mock_open, opener):
        """Test opening in new tab."""
        mock_open.return_value = True
        
        request = BrowserOpenRequest(url="https://example.com", new_tab=True)
        opener.open(request)
        
        mock_open.assert_called_with("https://example.com", new=2, autoraise=True)
    
    @patch('webbrowser.open')
    def test_open_in_new_window(self, mock_open, opener):
        """Test opening in new window."""
        mock_open.return_value = True
        
        request = BrowserOpenRequest(url="https://example.com", new_tab=False)
        opener.open(request)
        
        mock_open.assert_called_with("https://example.com", new=1, autoraise=True)
    
    @patch('webbrowser.open')
    def test_browser_failure(self, mock_open, opener):
        """Test handling browser failure."""
        mock_open.return_value = False
        
        request = BrowserOpenRequest(url="https://example.com")
        result = opener.open(request)
        
        assert result.status == BrowserOpenStatus.BROWSER_ERROR
    
    def test_invalid_url_not_opened(self, opener):
        """Test invalid URLs are not opened."""
        request = BrowserOpenRequest(url="not-a-url")
        result = opener.open(request)
        
        assert result.status == BrowserOpenStatus.INVALID_URL


class TestDuplicateTracking:
    """Tests for duplicate URL tracking."""
    
    @patch('webbrowser.open')
    def test_duplicate_detection(self, mock_open, opener):
        """Test duplicate URLs are detected."""
        mock_open.return_value = True
        
        request = BrowserOpenRequest(url="https://example.com")
        opener.open(request)
        
        result = opener.open(request)
        assert result.status == BrowserOpenStatus.DUPLICATE_URL
    
    @patch('webbrowser.open')
    def test_duplicate_with_trailing_slash(self, mock_open, opener):
        """Test duplicates detected with trailing slash difference."""
        mock_open.return_value = True
        
        opener.open(BrowserOpenRequest(url="https://example.com"))
        result = opener.open(BrowserOpenRequest(url="https://example.com/"))
        
        assert result.status == BrowserOpenStatus.DUPLICATE_URL
    
    @patch('webbrowser.open')
    def test_clear_history(self, mock_open, opener):
        """Test clearing URL history."""
        mock_open.return_value = True
        
        opener.open(BrowserOpenRequest(url="https://example.com"))
        opener.clear_history()
        
        result = opener.open(BrowserOpenRequest(url="https://example.com"))
        assert result.status == BrowserOpenStatus.SUCCESS

