"""
Field-Level Encryption Utilities.

Provides helpers for encrypting specific fields in data structures.

Copyright (c) 2025 ContextForge
"""

import logging
from typing import Any, Dict, List, Set

from . import get_encryptor, ENCRYPT_API_KEYS, ENCRYPT_QUERIES, ENCRYPT_CONTEXT

logger = logging.getLogger(__name__)

# Fields that should be encrypted when their respective flags are enabled
API_KEY_FIELDS = {'api_key', 'apikey', 'secret_key', 'token', 'password', 'secret'}
QUERY_FIELDS = {'query', 'question', 'prompt', 'user_input'}
CONTEXT_FIELDS = {'context', 'contexts', 'content', 'response', 'answer'}


class FieldEncryptor:
    """Handles field-level encryption for data structures."""
    
    def __init__(self):
        self._encryptor = get_encryptor()
        self._encrypted_marker = '$encrypted:'
    
    def encrypt_dict(self, data: Dict[str, Any], 
                     additional_fields: Set[str] = None) -> Dict[str, Any]:
        """
        Encrypt sensitive fields in a dictionary.
        
        Args:
            data: Dictionary to encrypt fields in
            additional_fields: Additional field names to encrypt
            
        Returns:
            New dictionary with encrypted fields
        """
        if not self._encryptor.is_enabled():
            return data
        
        result = {}
        fields_to_encrypt = self._get_fields_to_encrypt(additional_fields)
        
        for key, value in data.items():
            if key.lower() in fields_to_encrypt:
                result[key] = self._encrypt_value(value)
            elif isinstance(value, dict):
                result[key] = self.encrypt_dict(value, additional_fields)
            elif isinstance(value, list):
                result[key] = self._encrypt_list(value, additional_fields)
            else:
                result[key] = value
        
        return result
    
    def decrypt_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt encrypted fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted fields
            
        Returns:
            New dictionary with decrypted fields
        """
        if not self._encryptor.is_enabled():
            return data
        
        result = {}
        
        for key, value in data.items():
            if isinstance(value, str) and value.startswith(self._encrypted_marker):
                result[key] = self._decrypt_value(value)
            elif isinstance(value, dict):
                result[key] = self.decrypt_dict(value)
            elif isinstance(value, list):
                result[key] = self._decrypt_list(value)
            else:
                result[key] = value
        
        return result
    
    def _get_fields_to_encrypt(self, additional_fields: Set[str] = None) -> Set[str]:
        """Get the set of field names to encrypt."""
        fields = set()
        
        if ENCRYPT_API_KEYS:
            fields.update(API_KEY_FIELDS)
        if ENCRYPT_QUERIES:
            fields.update(QUERY_FIELDS)
        if ENCRYPT_CONTEXT:
            fields.update(CONTEXT_FIELDS)
        if additional_fields:
            fields.update(f.lower() for f in additional_fields)
        
        return fields
    
    def _encrypt_value(self, value: Any) -> Any:
        """Encrypt a single value."""
        if value is None:
            return value
        
        if isinstance(value, str):
            encrypted = self._encryptor.encrypt_string(value)
            return f"{self._encrypted_marker}{encrypted}"
        elif isinstance(value, (int, float, bool)):
            # Encrypt numeric/bool as string
            encrypted = self._encryptor.encrypt_string(str(value))
            return f"{self._encrypted_marker}{encrypted}"
        elif isinstance(value, list):
            return [self._encrypt_value(item) for item in value]
        elif isinstance(value, dict):
            return self.encrypt_dict(value)
        
        return value
    
    def _decrypt_value(self, value: str) -> str:
        """Decrypt a single value."""
        if not value.startswith(self._encrypted_marker):
            return value
        
        try:
            encrypted = value[len(self._encrypted_marker):]
            return self._encryptor.decrypt_string(encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            return value
    
    def _encrypt_list(self, items: List, additional_fields: Set[str] = None) -> List:
        """Encrypt items in a list."""
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(self.encrypt_dict(item, additional_fields))
            else:
                result.append(item)
        return result
    
    def _decrypt_list(self, items: List) -> List:
        """Decrypt items in a list."""
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(self.decrypt_dict(item))
            elif isinstance(item, str) and item.startswith(self._encrypted_marker):
                result.append(self._decrypt_value(item))
            else:
                result.append(item)
        return result


# Singleton
_field_encryptor = None

def get_field_encryptor() -> FieldEncryptor:
    """Get singleton field encryptor."""
    global _field_encryptor
    if _field_encryptor is None:
        _field_encryptor = FieldEncryptor()
    return _field_encryptor

