"""
ContextForge Data Encryption.

Provides encryption for privacy-sensitive deployments.

Features:
- AES-256-GCM encryption for data at rest
- Key management with rotation support
- Transparent encryption/decryption for stored data
- API key encryption
- Configurable encryption policies

Copyright (c) 2025 ContextForge
"""

import os

__version__ = "0.1.0"

# Configuration
ENABLE_ENCRYPTION = os.getenv("ENABLE_ENCRYPTION", "false").lower() in ("true", "1", "yes")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
ENCRYPT_API_KEYS = os.getenv("ENCRYPT_API_KEYS", "true").lower() in ("true", "1", "yes")
ENCRYPT_QUERIES = os.getenv("ENCRYPT_QUERIES", "false").lower() in ("true", "1", "yes")
ENCRYPT_CONTEXT = os.getenv("ENCRYPT_CONTEXT", "false").lower() in ("true", "1", "yes")


def get_encryptor():
    """Get the appropriate encryptor based on configuration."""
    if ENABLE_ENCRYPTION and ENCRYPTION_KEY:
        from .aes_encryptor import AESEncryptor
        return AESEncryptor(ENCRYPTION_KEY)
    else:
        from .noop_encryptor import NoOpEncryptor
        return NoOpEncryptor()

