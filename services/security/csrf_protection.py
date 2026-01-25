"""
CSRF Protection Module.

Provides CSRF token generation and validation for state-changing requests.

Copyright (c) 2025 ContextForge
"""

import os
import secrets
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse


# CSRF Configuration
CSRF_SECRET_KEY = os.getenv("CSRF_SECRET_KEY", secrets.token_urlsafe(32))
CSRF_TOKEN_EXPIRE_HOURS = int(os.getenv("CSRF_TOKEN_EXPIRE_HOURS", "24"))
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "true").lower() in ("true", "1", "yes")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "strict")  # strict, lax, none


class CSRFProtection:
    """CSRF protection manager."""
    
    def __init__(self):
        self.secret_key = CSRF_SECRET_KEY.encode()
        self.token_expire = timedelta(hours=CSRF_TOKEN_EXPIRE_HOURS)
    
    def generate_token(self, session_id: Optional[str] = None) -> str:
        """
        Generate CSRF token.
        
        Token format: {random_bytes}.{timestamp}.{signature}
        """
        # Generate random bytes
        random_bytes = secrets.token_urlsafe(16)
        
        # Add timestamp
        timestamp = int(datetime.utcnow().timestamp())
        
        # Create signature
        message = f"{random_bytes}.{timestamp}"
        if session_id:
            message = f"{message}.{session_id}"
        
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{random_bytes}.{timestamp}.{signature}"
    
    def validate_token(
        self,
        token: str,
        session_id: Optional[str] = None,
        max_age_seconds: Optional[int] = None
    ) -> bool:
        """
        Validate CSRF token.
        
        Args:
            token: CSRF token to validate
            session_id: Optional session ID to bind token to
            max_age_seconds: Maximum age of token in seconds
        
        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse token
            parts = token.split(".")
            if len(parts) != 3:
                return False
            
            random_bytes, timestamp_str, signature = parts
            timestamp = int(timestamp_str)
            
            # Check expiration
            if max_age_seconds is None:
                max_age_seconds = int(self.token_expire.total_seconds())
            
            token_age = int(datetime.utcnow().timestamp()) - timestamp
            if token_age > max_age_seconds:
                return False
            
            # Verify signature
            message = f"{random_bytes}.{timestamp}"
            if session_id:
                message = f"{message}.{session_id}"
            
            expected_signature = hmac.new(
                self.secret_key,
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        
        except (ValueError, AttributeError):
            return False
    
    def set_csrf_cookie(self, response: Response, token: str) -> None:
        """Set CSRF token in HTTP-only cookie."""
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=True,  # Prevent JavaScript access
            secure=CSRF_COOKIE_SECURE,  # HTTPS only in production
            samesite=CSRF_COOKIE_SAMESITE,  # CSRF protection
            max_age=int(self.token_expire.total_seconds())
        )
    
    def get_csrf_token_from_cookie(self, request: Request) -> Optional[str]:
        """Get CSRF token from cookie."""
        return request.cookies.get(CSRF_COOKIE_NAME)
    
    def get_csrf_token_from_header(self, request: Request) -> Optional[str]:
        """Get CSRF token from header."""
        return request.headers.get(CSRF_HEADER_NAME)
    
    def verify_csrf_token(self, request: Request, session_id: Optional[str] = None) -> None:
        """
        Verify CSRF token from request.
        
        Raises HTTPException if token is invalid or missing.
        """
        # Get token from header
        header_token = self.get_csrf_token_from_header(request)
        
        if not header_token:
            raise HTTPException(
                status_code=403,
                detail="Missing CSRF token in header"
            )
        
        # Get token from cookie
        cookie_token = self.get_csrf_token_from_cookie(request)
        
        # Validate header token
        if not self.validate_token(header_token, session_id):
            raise HTTPException(
                status_code=403,
                detail="Invalid or expired CSRF token"
            )
        
        # Double-submit cookie pattern: verify tokens match
        if cookie_token and not hmac.compare_digest(header_token, cookie_token):
            raise HTTPException(
                status_code=403,
                detail="CSRF token mismatch"
            )


# Singleton instance
_csrf_protection = None


def get_csrf_protection() -> CSRFProtection:
    """Get singleton CSRF protection instance."""
    global _csrf_protection
    if _csrf_protection is None:
        _csrf_protection = CSRFProtection()
    return _csrf_protection

