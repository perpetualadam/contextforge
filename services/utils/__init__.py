"""
ContextForge Utilities Module.

Provides shared utilities across all services:
- Timezone-aware datetime helpers
- Common type definitions
- Shared constants

Copyright (c) 2025 ContextForge
"""

from datetime import datetime, timezone, timedelta
from typing import Optional


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    Replaces deprecated datetime.utcnow() with timezone-aware alternative.
    
    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """
    Get current UTC time as ISO format string.
    
    Returns:
        ISO formatted UTC timestamp
    """
    return utc_now().isoformat()


def expires_at(seconds: int) -> datetime:
    """
    Calculate expiration time from now.
    
    Args:
        seconds: Number of seconds until expiration
        
    Returns:
        Timezone-aware datetime for expiration
    """
    return utc_now() + timedelta(seconds=seconds)


def is_expired(dt: Optional[datetime]) -> bool:
    """
    Check if a datetime has expired.
    
    Args:
        dt: Datetime to check (can be None)
        
    Returns:
        True if expired, False otherwise
    """
    if dt is None:
        return False
    
    # Handle naive datetime by assuming UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return utc_now() > dt


def duration_ms(start: datetime) -> int:
    """
    Calculate duration in milliseconds from start time to now.
    
    Args:
        start: Start datetime
        
    Returns:
        Duration in milliseconds
    """
    # Handle naive datetime
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    
    return int((utc_now() - start).total_seconds() * 1000)


# Re-export for convenience
__all__ = [
    'utc_now',
    'utc_timestamp', 
    'expires_at',
    'is_expired',
    'duration_ms',
]

