"""
JWT Authentication and Authorization Module.

Provides secure JWT-based authentication with role-based access control.

Copyright (c) 2025 ContextForge
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing (bcrypt with argon2 fallback)
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__memory_cost=65536,  # 64 MB
    argon2__time_cost=3,
    argon2__parallelism=4
)

security = HTTPBearer()


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    SERVICE = "service"  # For service-to-service auth


class User(BaseModel):
    """User model."""
    user_id: str
    username: str
    email: Optional[str] = None
    roles: List[UserRole] = Field(default_factory=lambda: [UserRole.USER])
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TokenData(BaseModel):
    """JWT token payload."""
    user_id: str
    username: str
    roles: List[str]
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for token revocation


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class JWTAuthManager:
    """JWT authentication manager."""
    
    def __init__(self):
        self.secret_key = JWT_SECRET_KEY
        self.algorithm = JWT_ALGORITHM
        self.access_token_expire = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        # In production, use Redis or database for token revocation
        self.revoked_tokens: set = set()
    
    def hash_password(self, password: str) -> str:
        """Hash password using argon2/bcrypt."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user: User) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        expire = now + self.access_token_expire
        
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "exp": expire,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "type": "access"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        expire = now + self.refresh_token_expire
        
        payload = {
            "user_id": user.user_id,
            "exp": expire,
            "iat": now,
            "jti": secrets.token_urlsafe(16),
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_token_pair(self, user: User) -> TokenPair:
        """Create access and refresh token pair."""
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_token_expire.total_seconds())
        )
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is revoked
            jti = payload.get("jti")
            if jti in self.revoked_tokens:
                raise HTTPException(status_code=401, detail="Token has been revoked")
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    def revoke_token(self, token: str) -> None:
        """Revoke a token (add to blacklist)."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            jti = payload.get("jti")
            if jti:
                self.revoked_tokens.add(jti)
        except jwt.JWTError:
            pass  # Invalid token, ignore

    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
        """Verify JWT token from Authorization header."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Missing authentication token")

        token = credentials.credentials
        return self.decode_token(token)

    def get_current_user(self, token_data: Dict[str, Any]) -> User:
        """Get current user from token data."""
        return User(
            user_id=token_data["user_id"],
            username=token_data["username"],
            roles=[UserRole(role) for role in token_data.get("roles", ["user"])]
        )

    def require_roles(self, required_roles: List[UserRole]):
        """Dependency to require specific roles."""
        def role_checker(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
            token_data = self.verify_token(credentials)
            user = self.get_current_user(token_data)

            # Check if user has any of the required roles
            user_role_values = [role.value for role in user.roles]
            required_role_values = [role.value for role in required_roles]

            if not any(role in user_role_values for role in required_role_values):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required roles: {required_role_values}"
                )

            return user

        return role_checker


# Singleton instance
_jwt_manager = None


def get_jwt_manager() -> JWTAuthManager:
    """Get singleton JWT manager."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTAuthManager()
    return _jwt_manager


# FastAPI dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """FastAPI dependency to get current authenticated user."""
    manager = get_jwt_manager()
    token_data = manager.verify_token(credentials)
    return manager.get_current_user(token_data)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency to require admin role."""
    if UserRole.ADMIN not in user.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_user(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency to require user role (or higher)."""
    allowed_roles = [UserRole.ADMIN, UserRole.USER]
    if not any(role in user.roles for role in allowed_roles):
        raise HTTPException(status_code=403, detail="User access required")
    return user

