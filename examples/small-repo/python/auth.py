"""
Authentication and Authorization Module

This module provides user authentication, session management, and authorization
functionality for the application. It includes password hashing, JWT token
generation, and role-based access control.
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum


class UserRole(Enum):
    """User roles for authorization."""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


@dataclass
class User:
    """User data model."""
    id: int
    username: str
    email: str
    password_hash: str
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


class AuthManager:
    """
    Manages user authentication and authorization.
    
    This class handles user login, logout, password verification,
    JWT token generation and validation, and role-based access control.
    """
    
    def __init__(self, secret_key: str, token_expiry_hours: int = 24):
        """
        Initialize the authentication manager.
        
        Args:
            secret_key: Secret key for JWT token signing
            token_expiry_hours: Hours until JWT tokens expire
        """
        self.secret_key = secret_key
        self.token_expiry_hours = token_expiry_hours
        self.algorithm = "HS256"
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256 with salt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password with salt
        """
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Stored password hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            salt, stored_hash = password_hash.split(":", 1)
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == stored_hash
        except ValueError:
            return False
    
    def authenticate_user(self, username: str, password: str, users_db: Dict[str, User]) -> User:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            users_db: Database of users (username -> User)
            
        Returns:
            Authenticated user object
            
        Raises:
            AuthenticationError: If authentication fails
        """
        user = users_db.get(username)
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        
        if not self.verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid password")
        
        # Update last login time
        user.last_login = datetime.utcnow()
        
        return user
    
    def generate_token(self, user: User) -> str:
        """
        Generate a JWT token for an authenticated user.
        
        Args:
            user: Authenticated user
            
        Returns:
            JWT token string
        """
        payload = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_token(self, token: str) -> Dict:
        """
        Validate and decode a JWT token.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
    
    def require_role(self, user_role: UserRole, required_roles: List[UserRole]) -> None:
        """
        Check if user has required role for authorization.
        
        Args:
            user_role: User's current role
            required_roles: List of roles that are allowed
            
        Raises:
            AuthorizationError: If user lacks required permissions
        """
        if user_role not in required_roles:
            raise AuthorizationError(f"Access denied. Required roles: {[r.value for r in required_roles]}")
    
    def login(self, username: str, password: str, users_db: Dict[str, User]) -> Dict[str, str]:
        """
        Complete login process: authenticate user and generate token.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            users_db: Database of users
            
        Returns:
            Dictionary containing access token and user info
            
        Raises:
            AuthenticationError: If login fails
        """
        user = self.authenticate_user(username, password, users_db)
        token = self.generate_token(user)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "expires_in": self.token_expiry_hours * 3600  # seconds
        }


def create_admin_user(auth_manager: AuthManager) -> User:
    """
    Create a default admin user for initial setup.
    
    Args:
        auth_manager: Authentication manager instance
        
    Returns:
        Admin user object
    """
    password_hash = auth_manager.hash_password("admin123")
    
    return User(
        id=1,
        username="admin",
        email="admin@example.com",
        password_hash=password_hash,
        role=UserRole.ADMIN,
        created_at=datetime.utcnow(),
        is_active=True
    )


# Example usage and testing
if __name__ == "__main__":
    # Initialize auth manager
    auth = AuthManager(secret_key="your-secret-key-here")
    
    # Create sample users
    admin_user = create_admin_user(auth)
    users_db = {"admin": admin_user}
    
    try:
        # Test login
        login_result = auth.login("admin", "admin123", users_db)
        print("Login successful:", login_result)
        
        # Test token validation
        token = login_result["access_token"]
        payload = auth.validate_token(token)
        print("Token valid:", payload)
        
        # Test authorization
        user_role = UserRole(payload["role"])
        auth.require_role(user_role, [UserRole.ADMIN])
        print("Authorization successful")
        
    except (AuthenticationError, AuthorizationError) as e:
        print("Auth error:", e)
