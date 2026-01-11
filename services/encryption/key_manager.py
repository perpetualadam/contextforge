"""
Encryption Key Manager.

Handles key storage, rotation, and management.

Copyright (c) 2025 ContextForge
"""

import base64
import hashlib
import logging
import os
import secrets
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import uuid

logger = logging.getLogger(__name__)


class KeyVersion(BaseModel):
    """Key version metadata."""
    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key_hash: str  # SHA256 hash for identification
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    rotated_to: Optional[str] = None  # Version ID of replacement


class KeyManager:
    """
    Manages encryption keys with support for rotation.
    
    Note: This is an in-memory implementation.
    For production, consider using a proper key management service (KMS).
    """
    
    def __init__(self):
        self._keys: Dict[str, bytes] = {}  # version_id -> key
        self._versions: List[KeyVersion] = []
        self._active_version_id: Optional[str] = None
    
    def generate_key(self) -> str:
        """Generate a new random encryption key."""
        key = secrets.token_bytes(32)
        return base64.b64encode(key).decode('ascii')
    
    def add_key(self, key: str, set_active: bool = True) -> KeyVersion:
        """
        Add a new key to the manager.
        
        Args:
            key: Base64-encoded encryption key
            set_active: Whether to make this the active key
            
        Returns:
            KeyVersion metadata
        """
        key_bytes = base64.b64decode(key)
        key_hash = hashlib.sha256(key_bytes).hexdigest()[:16]
        
        version = KeyVersion(key_hash=key_hash)
        
        self._keys[version.version_id] = key_bytes
        self._versions.append(version)
        
        if set_active:
            self._set_active(version.version_id)
        
        logger.info(f"Added key version {version.version_id} (hash: {key_hash})")
        return version
    
    def _set_active(self, version_id: str) -> None:
        """Set the active key version."""
        if version_id not in self._keys:
            raise ValueError(f"Key version {version_id} not found")
        
        self._active_version_id = version_id
    
    def get_active_key(self) -> Optional[bytes]:
        """Get the currently active encryption key."""
        if self._active_version_id:
            return self._keys.get(self._active_version_id)
        return None
    
    def get_key(self, version_id: str) -> Optional[bytes]:
        """Get a key by version ID."""
        return self._keys.get(version_id)
    
    def rotate_key(self, new_key: str = None) -> KeyVersion:
        """
        Rotate to a new key.
        
        Args:
            new_key: Base64-encoded new key, or None to generate one
            
        Returns:
            New KeyVersion metadata
        """
        if new_key is None:
            new_key = self.generate_key()
        
        # Mark current key as rotated
        old_version_id = self._active_version_id
        
        # Add new key
        new_version = self.add_key(new_key, set_active=True)
        
        # Update old version metadata
        if old_version_id:
            for version in self._versions:
                if version.version_id == old_version_id:
                    version.is_active = False
                    version.rotated_to = new_version.version_id
                    break
        
        logger.info(f"Key rotated from {old_version_id} to {new_version.version_id}")
        return new_version
    
    def list_versions(self) -> List[KeyVersion]:
        """List all key versions."""
        return self._versions.copy()
    
    def get_active_version(self) -> Optional[KeyVersion]:
        """Get the active key version metadata."""
        for version in self._versions:
            if version.version_id == self._active_version_id:
                return version
        return None
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a key version.
        
        Warning: This will make data encrypted with this key unrecoverable!
        """
        if version_id == self._active_version_id:
            raise ValueError("Cannot delete active key version")
        
        if version_id in self._keys:
            del self._keys[version_id]
            self._versions = [v for v in self._versions if v.version_id != version_id]
            logger.warning(f"Deleted key version {version_id}")
            return True
        return False


# Singleton
_key_manager = None

def get_key_manager() -> KeyManager:
    """Get singleton key manager."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
        
        # Initialize with environment key if set
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            try:
                _key_manager.add_key(env_key, set_active=True)
            except Exception as e:
                logger.error(f"Failed to initialize encryption key: {e}")
    
    return _key_manager

