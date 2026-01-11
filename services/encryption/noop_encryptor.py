"""
No-Op Encryptor (Passthrough).

Used when encryption is disabled.

Copyright (c) 2025 ContextForge
"""

from typing import Union
from .base import BaseEncryptor


class NoOpEncryptor(BaseEncryptor):
    """No-operation encryptor that passes data through unchanged."""
    
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Pass data through unchanged."""
        if isinstance(data, str):
            return data.encode('utf-8')
        return data
    
    def decrypt(self, data: bytes) -> bytes:
        """Pass data through unchanged."""
        return data
    
    def encrypt_string(self, text: str) -> str:
        """Return text unchanged."""
        return text
    
    def decrypt_string(self, encoded: str) -> str:
        """Return text unchanged."""
        return encoded
    
    def is_enabled(self) -> bool:
        """Encryption is not enabled."""
        return False
    
    def rotate_key(self, new_key: bytes) -> None:
        """No-op for key rotation."""
        pass

