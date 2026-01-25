"""
ContextForge Browser Opener - URL opening tool for system browser.

Provides browser URL opening capabilities:
- Open URLs in the default system browser
- Cross-platform support (Windows, macOS, Linux)
- URL validation and security checks
- Tracking of opened URLs to prevent duplicates

Copyright (c) 2025 ContextForge
"""

import logging
import re
import webbrowser
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserOpenStatus(Enum):
    """Status of a browser open operation."""
    SUCCESS = "success"
    INVALID_URL = "invalid_url"
    BLOCKED_DOMAIN = "blocked_domain"
    DUPLICATE_URL = "duplicate_url"
    BROWSER_ERROR = "browser_error"
    ERROR = "error"


@dataclass
class BrowserOpenRequest:
    """Request to open a URL in the browser."""
    url: str
    new_tab: bool = True  # Open in new tab vs new window
    autoraise: bool = True  # Bring browser to foreground


@dataclass
class BrowserOpenResult:
    """Result of a browser open operation."""
    status: BrowserOpenStatus
    url: str
    message: str
    opened_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BrowserOpener:
    """
    Browser URL opener for system default browser.
    
    Provides:
    - Cross-platform browser opening
    - URL validation and sanitization
    - Security checks for blocked domains
    - Duplicate URL tracking
    
    Example usage:
        opener = BrowserOpener()
        result = opener.open(BrowserOpenRequest(url="https://example.com"))
        print(result.status, result.message)
    
    Security considerations:
        - Only allows http/https URLs by default
        - Blocks potentially dangerous domains
        - Validates URL format before opening
        - Tracks opened URLs to prevent spam
    """
    
    # Allowed URL schemes
    ALLOWED_SCHEMES = {"http", "https"}
    
    # Blocked domains (security/safety)
    BLOCKED_DOMAINS: Set[str] = set()  # Can be configured
    
    # Maximum URLs to track for duplicate detection
    MAX_TRACKED_URLS = 100
    
    def __init__(self, track_duplicates: bool = True):
        """
        Initialize browser opener.
        
        Args:
            track_duplicates: Whether to track and warn about duplicate URLs
        """
        self._track_duplicates = track_duplicates
        self._opened_urls: List[str] = []
    
    def _validate_url(self, url: str) -> tuple[bool, str]:
        """
        Validate a URL for security and format.
        
        Args:
            url: The URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, "URL cannot be empty"
        
        url = url.strip()
        
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
                return False, f"URL scheme '{parsed.scheme}' not allowed. Use http or https."
            
            # Check for valid hostname
            if not parsed.netloc:
                return False, "URL must include a domain name"
            
            # Check blocked domains
            domain = parsed.netloc.lower()
            if any(blocked in domain for blocked in self.BLOCKED_DOMAINS):
                return False, f"Domain '{domain}' is blocked for security"
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid URL format: {e}"
    
    def _is_duplicate(self, url: str) -> bool:
        """Check if URL was recently opened."""
        normalized = url.rstrip('/').lower()
        return normalized in [u.rstrip('/').lower() for u in self._opened_urls]
    
    def _track_url(self, url: str) -> None:
        """Track an opened URL."""
        self._opened_urls.append(url)
        if len(self._opened_urls) > self.MAX_TRACKED_URLS:
            self._opened_urls = self._opened_urls[-self.MAX_TRACKED_URLS:]
    
    def open(self, request: BrowserOpenRequest) -> BrowserOpenResult:
        """
        Open a URL in the default system browser.
        
        Args:
            request: BrowserOpenRequest with URL and options
            
        Returns:
            BrowserOpenResult with status and details
        """
        url = request.url.strip()
        
        # Validate URL
        is_valid, error = self._validate_url(url)
        if not is_valid:
            return BrowserOpenResult(
                status=BrowserOpenStatus.INVALID_URL,
                url=url,
                message=error
            )
        
        # Check for duplicate
        if self._track_duplicates and self._is_duplicate(url):
            return BrowserOpenResult(
                status=BrowserOpenStatus.DUPLICATE_URL,
                url=url,
                message="URL was already opened in this session"
            )

        try:
            # Determine browser opening method
            if request.new_tab:
                # Open in new tab (mode 2)
                success = webbrowser.open(url, new=2, autoraise=request.autoraise)
            else:
                # Open in new window (mode 1)
                success = webbrowser.open(url, new=1, autoraise=request.autoraise)

            if success:
                self._track_url(url)
                logger.info(f"Opened URL in browser: {url}")
                return BrowserOpenResult(
                    status=BrowserOpenStatus.SUCCESS,
                    url=url,
                    message="URL opened successfully in browser"
                )
            else:
                return BrowserOpenResult(
                    status=BrowserOpenStatus.BROWSER_ERROR,
                    url=url,
                    message="Browser reported failure to open URL"
                )

        except webbrowser.Error as e:
            logger.error(f"Browser error: {e}")
            return BrowserOpenResult(
                status=BrowserOpenStatus.BROWSER_ERROR,
                url=url,
                message=f"Browser error: {e}"
            )
        except Exception as e:
            logger.error(f"Error opening URL: {e}")
            return BrowserOpenResult(
                status=BrowserOpenStatus.ERROR,
                url=url,
                message=f"Error: {e}"
            )

    def clear_history(self) -> None:
        """Clear the tracked URL history."""
        self._opened_urls.clear()

    def get_opened_urls(self) -> List[str]:
        """Get list of URLs opened in this session."""
        return self._opened_urls.copy()

    def add_blocked_domain(self, domain: str) -> None:
        """Add a domain to the blocked list."""
        self.BLOCKED_DOMAINS.add(domain.lower())

    def remove_blocked_domain(self, domain: str) -> None:
        """Remove a domain from the blocked list."""
        self.BLOCKED_DOMAINS.discard(domain.lower())


# Factory function
_opener_instance: Optional[BrowserOpener] = None


def get_browser_opener() -> BrowserOpener:
    """
    Get or create a BrowserOpener instance.

    Returns:
        BrowserOpener instance
    """
    global _opener_instance
    if _opener_instance is None:
        _opener_instance = BrowserOpener()
    return _opener_instance


def reset_browser_opener() -> None:
    """Reset the singleton instance. Useful for testing."""
    global _opener_instance
    _opener_instance = None

