# API Reference

This document provides comprehensive documentation for the ContextForge Example API endpoints, including request/response formats, authentication requirements, and usage examples.

## Base URL

```
http://localhost:8000
```

## Authentication

The API uses JWT (JSON Web Token) based authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## Response Format

All API responses follow a consistent JSON format:

**Success Response:**
```json
{
    "data": { ... },
    "status": 200
}
```

**Error Response:**
```json
{
    "error": "Error Type",
    "detail": "Detailed error message",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## Endpoints

### General

#### GET /
Get API information and available endpoints.

**Response:**
```json
{
    "message": "ContextForge Example API",
    "version": "1.0.0",
    "docs": "/docs",
    "health": "/health"
}
```

#### GET /health
Check API health status.

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-01T12:00:00Z",
    "service": "example_api",
    "database": "connected"
}
```

### Authentication

#### POST /auth/login
Authenticate user and receive access token.

**Request Body:**
```json
{
    "username": "string",
    "password": "string"
}
```

**Response:**
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "user_id": "1",
    "username": "admin",
    "role": "admin",
    "expires_in": 86400
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials
- `401 Unauthorized`: User account disabled

**Example:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}'
```

#### GET /auth/me
Get current authenticated user information.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin",
    "created_at": "2024-01-01T12:00:00Z",
    "last_login": "2024-01-01T13:00:00Z",
    "is_active": true
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or expired token
- `404 Not Found`: User not found

**Example:**
```bash
curl -X GET "http://localhost:8000/auth/me" \
     -H "Authorization: Bearer <your-token>"
```

### User Management

#### GET /users
List all users (admin only).

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Query Parameters:**
- `skip` (integer, optional): Number of records to skip (default: 0)
- `limit` (integer, optional): Maximum records to return (default: 100)

**Response:**
```json
[
    {
        "id": 1,
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "created_at": "2024-01-01T12:00:00Z",
        "last_login": "2024-01-01T13:00:00Z",
        "is_active": true
    },
    {
        "id": 2,
        "username": "user1",
        "email": "user1@example.com",
        "role": "user",
        "created_at": "2024-01-01T14:00:00Z",
        "last_login": null,
        "is_active": true
    }
]
```

**Error Responses:**
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions

**Example:**
```bash
curl -X GET "http://localhost:8000/users?skip=0&limit=10" \
     -H "Authorization: Bearer <admin-token>"
```

#### POST /users
Create a new user (admin only).

**Headers:**
```
Authorization: Bearer <admin-token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "securepassword",
    "role": "user"
}
```

**Response:**
```json
{
    "id": 3,
    "username": "newuser",
    "email": "newuser@example.com",
    "role": "user",
    "created_at": "2024-01-01T15:00:00Z",
    "last_login": null,
    "is_active": true
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input data
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `409 Conflict`: Username or email already exists

**Example:**
```bash
curl -X POST "http://localhost:8000/users" \
     -H "Authorization: Bearer <admin-token>" \
     -H "Content-Type: application/json" \
     -d '{
         "username": "newuser",
         "email": "newuser@example.com",
         "password": "securepassword",
         "role": "user"
     }'
```

#### PUT /users/{user_id}
Update an existing user (admin only).

**Headers:**
```
Authorization: Bearer <admin-token>
Content-Type: application/json
```

**Path Parameters:**
- `user_id` (integer): ID of the user to update

**Request Body:**
```json
{
    "email": "updated@example.com",
    "role": "admin",
    "is_active": false
}
```

**Response:**
```json
{
    "id": 2,
    "username": "user1",
    "email": "updated@example.com",
    "role": "admin",
    "created_at": "2024-01-01T14:00:00Z",
    "last_login": null,
    "is_active": false
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input data or no update data provided
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User not found

**Example:**
```bash
curl -X PUT "http://localhost:8000/users/2" \
     -H "Authorization: Bearer <admin-token>" \
     -H "Content-Type: application/json" \
     -d '{
         "email": "updated@example.com",
         "is_active": false
     }'
```

#### DELETE /users/{user_id}
Delete a user (admin only).

**Headers:**
```
Authorization: Bearer <admin-token>
```

**Path Parameters:**
- `user_id` (integer): ID of the user to delete

**Response:**
```
204 No Content
```

**Error Responses:**
- `400 Bad Request`: Cannot delete own account
- `401 Unauthorized`: Invalid token
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: User not found

**Example:**
```bash
curl -X DELETE "http://localhost:8000/users/2" \
     -H "Authorization: Bearer <admin-token>"
```

## Data Models

### User Model

```json
{
    "id": "integer",
    "username": "string",
    "email": "string (email format)",
    "role": "string (admin|user|guest)",
    "created_at": "string (ISO 8601 datetime)",
    "last_login": "string (ISO 8601 datetime) | null",
    "is_active": "boolean"
}
```

### Login Request Model

```json
{
    "username": "string (required)",
    "password": "string (required)"
}
```

### User Create Request Model

```json
{
    "username": "string (required)",
    "email": "string (required, email format)",
    "password": "string (required)",
    "role": "string (optional, default: user)"
}
```

### User Update Request Model

```json
{
    "email": "string (optional, email format)",
    "role": "string (optional)",
    "is_active": "boolean (optional)"
}
```

## Error Codes

| Status Code | Error Type | Description |
|-------------|------------|-------------|
| 400 | Bad Request | Invalid input data or malformed request |
| 401 | Unauthorized | Authentication required or invalid token |
| 403 | Forbidden | Insufficient permissions for the operation |
| 404 | Not Found | Requested resource does not exist |
| 409 | Conflict | Resource already exists (e.g., duplicate username) |
| 422 | Unprocessable Entity | Validation error in request data |
| 500 | Internal Server Error | Unexpected server error |

## Rate Limiting

Currently, no rate limiting is implemented. In production, consider implementing:

- **Authentication endpoints**: 5 requests per minute per IP
- **User management**: 100 requests per minute per user
- **General endpoints**: 1000 requests per minute per user

## Security Considerations

### Authentication Security

- JWT tokens expire after 24 hours (configurable)
- Passwords are hashed using SHA-256 with salt
- Failed login attempts should be logged (not implemented)

### Authorization Security

- Role-based access control (RBAC)
- Admin-only endpoints are protected
- Users cannot modify other users' data

### Input Validation

- All inputs are validated using Pydantic models
- Email format validation
- SQL injection prevention through parameterized queries

## Usage Examples

### Complete User Management Flow

```bash
# 1. Login as admin
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "admin123"}')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

# 2. Get current user info
curl -X GET "http://localhost:8000/auth/me" \
    -H "Authorization: Bearer $TOKEN"

# 3. List all users
curl -X GET "http://localhost:8000/users" \
    -H "Authorization: Bearer $TOKEN"

# 4. Create a new user
curl -X POST "http://localhost:8000/users" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "role": "user"
    }'

# 5. Update the user
curl -X PUT "http://localhost:8000/users/2" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"is_active": false}'

# 6. Delete the user
curl -X DELETE "http://localhost:8000/users/2" \
    -H "Authorization: Bearer $TOKEN"
```

### Error Handling Example

```javascript
// TypeScript/JavaScript example
async function createUser(userData) {
    try {
        const response = await fetch('/users', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || error.error);
        }

        return await response.json();
    } catch (error) {
        console.error('User creation failed:', error.message);
        throw error;
    }
}
```

## Testing

### Health Check Test

```bash
curl -f http://localhost:8000/health || echo "API is down"
```

### Authentication Test

```bash
# Test valid login
curl -X POST "http://localhost:8000/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "admin123"}' \
    | jq '.access_token'

# Test invalid login
curl -X POST "http://localhost:8000/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username": "admin", "password": "wrong"}' \
    | jq '.error'
```

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
