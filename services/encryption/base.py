"""
Base Encryption Interface.

Copyright (c) 2025 ContextForge
"""

from abc import ABC, abstractmethod
from typing import Union


class BaseEncryptor(ABC):
    """Base interface for encryption implementations."""
    
    @abstractmethod
    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """
        Encrypt data.
        
        Args:
            data: Plain text or bytes to encrypt
            
        Returns:
            Encrypted bytes (includes nonce/IV)
        """
        pass
    
    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt data.
        
        Args:
            data: Encrypted bytes (includes nonce/IV)
            
        Returns:
            Decrypted bytes
        """
        pass
    
    def encrypt_string(self, text: str) -> str:
        """Encrypt a string and return base64-encoded result."""
        import base64
        encrypted = self.encrypt(text.encode('utf-8'))
        return base64.b64encode(encrypted).decode('ascii')
    
    def decrypt_string(self, encoded: str) -> str:
        """Decrypt a base64-encoded string."""
        import base64
        encrypted = base64.b64decode(encoded.encode('ascii'))
        return self.decrypt(encrypted).decode('utf-8')
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if encryption is enabled."""
        pass
    
    @abstractmethod
    def rotate_key(self, new_key: bytes) -> None:
        """
        Rotate encryption key.
        
        Note: Existing encrypted data must be re-encrypted with new key.
        """
        pass

