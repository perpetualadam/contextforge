"""
Tests for Encryption Service.
"""

import pytest
import os
import sys

# Add the services directory to path for importing
services_path = os.path.join(os.path.dirname(__file__), '..', 'services')
if services_path not in sys.path:
    sys.path.insert(0, services_path)

from encryption.base import BaseEncryptor
from encryption.aes_encryptor import AESEncryptor
from encryption.noop_encryptor import NoOpEncryptor
from encryption.field_encryption import FieldEncryptor, get_field_encryptor
from encryption.key_manager import KeyManager, get_key_manager


class TestNoOpEncryptor:
    """Test NoOp encryptor (pass-through)."""

    def test_encrypt_returns_same_data(self):
        """Test that encryption returns the same data."""
        encryptor = NoOpEncryptor()
        data = "test data"
        encrypted = encryptor.encrypt(data)
        # NoOpEncryptor returns bytes for consistency
        assert encrypted == data.encode('utf-8') or encrypted == data

    def test_decrypt_returns_same_data(self):
        """Test that decryption returns the same data."""
        encryptor = NoOpEncryptor()
        data = "test data"
        decrypted = encryptor.decrypt(data)
        assert decrypted == data

    def test_is_enabled_returns_false(self):
        """Test that is_enabled returns False for NoOp."""
        encryptor = NoOpEncryptor()
        assert encryptor.is_enabled() is False


class TestAESEncryptor:
    """Test AES encryptor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.key = "test-secret-key-for-encryption"
        self.encryptor = AESEncryptor(key=self.key)

    def test_encrypt_and_decrypt(self):
        """Test basic encryption and decryption."""
        original = "sensitive data to encrypt"
        encrypted = self.encryptor.encrypt(original)

        assert encrypted != original.encode('utf-8')
        assert self.encryptor.is_enabled()

        decrypted = self.encryptor.decrypt(encrypted)
        assert decrypted == original.encode('utf-8')

    def test_encrypt_different_results(self):
        """Test that encrypting same data gives different ciphertext (due to IV)."""
        data = "test data"
        encrypted1 = self.encryptor.encrypt(data)
        encrypted2 = self.encryptor.encrypt(data)

        # Should be different due to random nonce
        assert encrypted1 != encrypted2

        # But both should decrypt to same value
        assert self.encryptor.decrypt(encrypted1) == data.encode('utf-8')
        assert self.encryptor.decrypt(encrypted2) == data.encode('utf-8')

    def test_unicode_support(self):
        """Test encryption of unicode data."""
        original = "Hello 世界 🌍 привет"
        encrypted = self.encryptor.encrypt(original)
        decrypted = self.encryptor.decrypt(encrypted)
        assert decrypted == original.encode('utf-8')

    def test_empty_string(self):
        """Test encryption of empty string."""
        original = ""
        encrypted = self.encryptor.encrypt(original)
        decrypted = self.encryptor.decrypt(encrypted)
        assert decrypted == original.encode('utf-8')

    def test_long_data(self):
        """Test encryption of long data."""
        original = "x" * 100000
        encrypted = self.encryptor.encrypt(original)
        decrypted = self.encryptor.decrypt(encrypted)
        assert decrypted == original.encode('utf-8')

    def test_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        original = "secret data"
        encrypted = self.encryptor.encrypt(original)

        wrong_encryptor = AESEncryptor(key="wrong-key")

        with pytest.raises(Exception):
            wrong_encryptor.decrypt(encrypted)


class TestFieldEncryptor:
    """Test field-level encryption."""

    def test_field_encryptor_singleton(self):
        """Test that get_field_encryptor returns singleton."""
        fe1 = get_field_encryptor()
        fe2 = get_field_encryptor()
        assert fe1 is fe2

    def test_encrypt_dict_basic(self):
        """Test encrypting a dictionary."""
        field_encryptor = FieldEncryptor()
        data = {
            "name": "John",
            "email": "john@example.com"
        }

        # FieldEncryptor uses global encryptor settings
        encrypted = field_encryptor.encrypt_dict(data)
        # Result depends on encryption settings
        assert isinstance(encrypted, dict)

    def test_decrypt_dict_basic(self):
        """Test decrypting a dictionary."""
        field_encryptor = FieldEncryptor()
        data = {
            "name": "John",
            "email": "john@example.com"
        }

        decrypted = field_encryptor.decrypt_dict(data)
        assert isinstance(decrypted, dict)


class TestKeyManager:
    """Test key management."""

    def test_generate_key(self):
        """Test key generation."""
        manager = KeyManager()
        key = manager.generate_key()
        assert len(key) >= 32  # Base64 encoded 256-bit key

    def test_add_key(self):
        """Test adding a key."""
        manager = KeyManager()
        key = manager.generate_key()
        version = manager.add_key(key)

        assert version is not None
        assert version.key_hash is not None

    def test_get_active_key(self):
        """Test getting active key."""
        manager = KeyManager()
        key = manager.generate_key()
        manager.add_key(key, set_active=True)

        active = manager.get_active_key()
        assert active is not None

    def test_key_rotation(self):
        """Test key rotation."""
        manager = KeyManager()

        # Add initial key
        initial_key = manager.generate_key()
        manager.add_key(initial_key, set_active=True)
        old_version = manager.get_active_version()

        # Rotate to new key
        new_version = manager.rotate_key()

        assert new_version.version_id != old_version.version_id
        assert manager.get_active_version().version_id == new_version.version_id

    def test_list_versions(self):
        """Test listing key versions."""
        manager = KeyManager()
        key1 = manager.generate_key()
        key2 = manager.generate_key()

        manager.add_key(key1)
        manager.add_key(key2)

        versions = manager.list_versions()
        assert len(versions) >= 2

