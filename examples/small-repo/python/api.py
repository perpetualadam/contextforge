"""
REST API Endpoints Module

This module defines the REST API endpoints for the application using FastAPI.
It includes user management, authentication, and data access endpoints with
proper error handling, validation, and documentation.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .auth import AuthManager, User, UserRole, AuthenticationError, AuthorizationError
from .database import DatabaseManager, create_database_manager


# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ContextForge Example API",
    description="Example REST API demonstrating authentication and data access patterns",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security scheme
security = HTTPBearer()

# Global instances (in production, use dependency injection)
auth_manager = AuthManager(secret_key="your-secret-key-here")
db_manager = create_database_manager()


# Pydantic models for request/response
class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str
    expires_in: int


class UserCreate(BaseModel):
    """User creation request model."""
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.USER


class UserResponse(BaseModel):
    """User response model."""
    id: int
    username: str
    email: str
    role: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool


class UserUpdate(BaseModel):
    """User update request model."""
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: str
    timestamp: datetime


# Dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        User payload from JWT token
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        payload = auth_manager.validate_token(token)
        return payload
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require admin role for endpoint access.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User payload if authorized
        
    Raises:
        HTTPException: If user lacks admin privileges
    """
    try:
        user_role = UserRole(current_user["role"])
        auth_manager.require_role(user_role, [UserRole.ADMIN])
        return current_user
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ContextForge Example API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "example_api",
        "database": "connected"
    }


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return access token.
    
    Args:
        request: Login credentials
        
    Returns:
        Login response with access token
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Get users from database (simplified for example)
        users_db = {}  # In real app, load from database
        
        # For demo, create a test user
        if request.username == "admin" and request.password == "admin123":
            from .auth import create_admin_user
            admin_user = create_admin_user(auth_manager)
            users_db["admin"] = admin_user
        
        login_result = auth_manager.login(request.username, request.password, users_db)
        
        return LoginResponse(**login_result)
        
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User information
    """
    # In real app, fetch from database
    user_data = db_manager.fetch_one("SELECT * FROM users WHERE id = ?", (current_user["user_id"],))
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        role=user_data["role"],
        created_at=datetime.fromisoformat(user_data["created_at"]),
        last_login=datetime.fromisoformat(user_data["last_login"]) if user_data["last_login"] else None,
        is_active=bool(user_data["is_active"])
    )


@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    List all users (admin only).
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current authenticated admin user
        
    Returns:
        List of users
    """
    users_data = db_manager.fetch_all(
        "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, skip)
    )
    
    return [
        UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            created_at=datetime.fromisoformat(user["created_at"]),
            last_login=datetime.fromisoformat(user["last_login"]) if user["last_login"] else None,
            is_active=bool(user["is_active"])
        )
        for user in users_data
    ]


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Create a new user (admin only).
    
    Args:
        user_data: User creation data
        current_user: Current authenticated admin user
        
    Returns:
        Created user information
        
    Raises:
        HTTPException: If user creation fails
    """
    try:
        # Hash password
        password_hash = auth_manager.hash_password(user_data.password)
        
        # Insert user into database
        user_id = db_manager.insert("users", {
            "username": user_data.username,
            "email": user_data.email,
            "password_hash": password_hash,
            "role": user_data.role.value,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        })
        
        # Fetch created user
        created_user = db_manager.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        
        return UserResponse(
            id=created_user["id"],
            username=created_user["username"],
            email=created_user["email"],
            role=created_user["role"],
            created_at=datetime.fromisoformat(created_user["created_at"]),
            last_login=None,
            is_active=bool(created_user["is_active"])
        )
        
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User creation failed"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
