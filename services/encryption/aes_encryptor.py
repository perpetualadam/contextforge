"""
AES-256-GCM Encryption Implementation.

Provides secure encryption for sensitive data.

Copyright (c) 2025 ContextForge
"""

import base64
import logging
import os
import secrets
from typing import Union

from .base import BaseEncryptor

logger = logging.getLogger(__name__)

# Constants
NONCE_SIZE = 12  # 96 bits for GCM
TAG_SIZE = 16    # 128 bits authentication tag
KEY_SIZE = 32    # 256 bits


class AESEncryptor(BaseEncryptor):
    """
    AES-256-GCM encryption implementation.
    
    Uses cryptography library for secure encryption.
    Each encryption generates a unique nonce for security.
    """
    
    def __init__(self, key: Union[str, bytes]):
        """
        Initialize encryptor with key.
        
        Args:
            key: Base64-encoded key string or 32-byte key
        """
        self._key = self._normalize_key(key)
        self._cipher = None
        self._setup_cipher()
    
    def _normalize_key(self, key: Union[str, bytes]) -> bytes:
        """Normalize key to 32 bytes."""
        if isinstance(key, str):
            # Try base64 decode first
            try:
                decoded = base64.b64decode(key)
                if len(decoded) == KEY_SIZE:
                    return decoded
            except Exception:
                pass
            
            # Use key as password, derive key using PBKDF2
            return self._derive_key(key.encode('utf-8'))
        
        if len(key) == KEY_SIZE:
            return key
        
        return self._derive_key(key)
    
    def _derive_key(self, password: bytes, salt: bytes = None) -> bytes:
        """Derive a key from password using PBKDF2."""
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            if salt is None:
                salt = b'contextforge_salt_v1'  # Static salt for consistency
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=KEY_SIZE,
                salt=salt,
                iterations=100000,
            )
            return kdf.derive(password)
        except ImportError:
            logger.error("cryptography library not installed")
            raise
    
    def _setup_cipher(self):
        """Set up cipher for encryption/decryption."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            self._cipher = AESGCM(self._key)
        except ImportError:
            logger.error("cryptography library not installed. Install with: pip install cryptography")
            raise
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        Encrypt data using AES-256-GCM.
        
        Returns: nonce (12 bytes) + ciphertext + tag (16 bytes)
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Generate random nonce for each encryption
        nonce = secrets.token_bytes(NONCE_SIZE)
        
        # Encrypt with authentication
        ciphertext = self._cipher.encrypt(nonce, data, None)
        
        # Prepend nonce to ciphertext
        return nonce + ciphertext
    
    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM.
        
        Args:
            data: nonce (12 bytes) + ciphertext + tag
        """
        if len(data) < NONCE_SIZE + TAG_SIZE:
            raise ValueError("Invalid encrypted data: too short")
        
        # Extract nonce and ciphertext
        nonce = data[:NONCE_SIZE]
        ciphertext = data[NONCE_SIZE:]
        
        # Decrypt and verify authentication tag
        return self._cipher.decrypt(nonce, ciphertext, None)
    
    def is_enabled(self) -> bool:
        """Encryption is enabled."""
        return True
    
    def rotate_key(self, new_key: bytes) -> None:
        """
        Rotate to a new encryption key.
        
        Note: This only updates the key in memory.
        Existing encrypted data must be re-encrypted separately.
        """
        self._key = self._normalize_key(new_key)
        self._setup_cipher()
        logger.info("Encryption key rotated")


def generate_key() -> str:
    """Generate a new random encryption key."""
    key = secrets.token_bytes(KEY_SIZE)
    return base64.b64encode(key).decode('ascii')


def validate_key(key: str) -> bool:
    """Validate an encryption key."""
    try:
        decoded = base64.b64decode(key)
        return len(decoded) == KEY_SIZE
    except Exception:
        return False

