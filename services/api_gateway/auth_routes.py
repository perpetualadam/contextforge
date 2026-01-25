"""
Authentication Routes for API Gateway.

Provides login, logout, token refresh, and user management endpoints.

Copyright (c) 2025 ContextForge
"""

import os
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel, Field, EmailStr

from services.security import (
    get_jwt_manager,
    get_csrf_protection,
    get_audit_logger,
    User,
    UserRole,
    TokenPair,
    AuditEventType
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory user store (replace with database in production)
# Password: "admin123" hashed with argon2
DEMO_USERS = {
    "admin": {
        "user_id": "user_001",
        "username": "admin",
        "email": "admin@contextforge.local",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",  # Replace with actual hash
        "roles": [UserRole.ADMIN],
        "is_active": True
    }
}


class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    old_password: str = Field(..., min_length=8, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


@router.post("/login", response_model=TokenPair)
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response
):
    """
    Authenticate user and return JWT tokens.
    
    Returns access token and refresh token.
    """
    jwt_manager = get_jwt_manager()
    audit_logger = get_audit_logger()
    csrf_protection = get_csrf_protection()
    
    client_ip = http_request.client.host if http_request.client else "unknown"
    
    # Validate credentials
    user_data = DEMO_USERS.get(request.username)
    
    if not user_data:
        # Log failed login
        audit_logger.log_security_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id=None,
            username=request.username,
            client_ip=client_ip,
            details={"reason": "user_not_found"},
            severity="warning"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not jwt_manager.verify_password(request.password, user_data["password_hash"]):
        # Log failed login
        audit_logger.log_security_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id=user_data["user_id"],
            username=request.username,
            client_ip=client_ip,
            details={"reason": "invalid_password"},
            severity="warning"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check if user is active
    if not user_data.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is disabled")
    
    # Create user object
    user = User(
        user_id=user_data["user_id"],
        username=user_data["username"],
        email=user_data.get("email"),
        roles=user_data["roles"]
    )
    
    # Generate tokens
    token_pair = jwt_manager.create_token_pair(user)
    
    # Generate and set CSRF token
    csrf_token = csrf_protection.generate_token(user.user_id)
    csrf_protection.set_csrf_cookie(response, csrf_token)
    
    # Log successful login
    audit_logger.log_security_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        user_id=user.user_id,
        username=user.username,
        client_ip=client_ip,
        details={"roles": [role.value for role in user.roles]},
        severity="info"
    )
    
    return token_pair


@router.post("/logout")
async def logout(
    http_request: Request,
    response: Response,
    user: User = Depends(get_current_user)
):
    """
    Logout user and revoke tokens.
    """
    jwt_manager = get_jwt_manager()
    audit_logger = get_audit_logger()
    
    # Get token from header
    auth_header = http_request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        jwt_manager.revoke_token(token)
    
    # Clear CSRF cookie
    response.delete_cookie("csrf_token")
    
    # Log logout
    audit_logger.log_security_event(
        event_type=AuditEventType.LOGOUT,
        user_id=user.user_id,
        username=user.username,
        client_ip=http_request.client.host if http_request.client else "unknown",
        details={},
        severity="info"
    )
    
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(request: TokenRefreshRequest):
    """
    Refresh access token using refresh token.
    """
    jwt_manager = get_jwt_manager()
    
    # Decode refresh token
    token_data = jwt_manager.decode_token(request.refresh_token)
    
    # Verify it's a refresh token
    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    
    # Create new user object
    user = User(
        user_id=token_data["user_id"],
        username=token_data.get("username", "unknown"),
        roles=[UserRole.USER]  # Load from database in production
    )
    
    # Generate new token pair
    token_pair = jwt_manager.create_token_pair(user)

    return token_pair


@router.get("/csrf-token")
async def get_csrf_token(response: Response, user: User = Depends(get_current_user)):
    """
    Get CSRF token for authenticated user.

    Returns CSRF token in response body and sets it in cookie.
    """
    csrf_protection = get_csrf_protection()

    # Generate CSRF token
    csrf_token = csrf_protection.generate_token(user.user_id)

    # Set in cookie
    csrf_protection.set_csrf_cookie(response, csrf_token)

    return {"csrf_token": csrf_token}


@router.get("/me", response_model=User)
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return user


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user)
):
    """Change user password."""
    jwt_manager = get_jwt_manager()

    # In production, load user from database
    user_data = DEMO_USERS.get(user.username)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify old password
    if not jwt_manager.verify_password(request.old_password, user_data["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid old password")

    # Hash new password
    new_hash = jwt_manager.hash_password(request.new_password)

    # Update password (in database in production)
    user_data["password_hash"] = new_hash

    return {"message": "Password changed successfully"}

