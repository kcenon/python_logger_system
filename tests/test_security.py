"""Tests for security module - encryption and key management"""

import pytest
import tempfile
import os
import base64
from pathlib import Path

from logger_module import LoggerBuilder, LogLevel
from logger_module.core.log_entry import LogEntry
from logger_module.writers import FileWriter

# Skip all tests if cryptography is not installed
pytest.importorskip("cryptography")

from logger_module.security import (
    EncryptionAlgorithm,
    EncryptionConfig,
    EncryptedWriter,
    SecureKeyStorage,
    generate_key,
    load_key_from_env,
    load_key_from_file,
    save_key_to_file,
    key_to_base64,
    key_from_base64,
    LogDecryptor,
)


class TestEncryptionConfig:
    """Test encryption configuration."""

    def test_valid_key_length(self):
        """Test that 32-byte key is accepted."""
        key = generate_key()
        config = EncryptionConfig(key=key)
        config.validate()

    def test_invalid_key_length(self):
        """Test that non-32-byte key is rejected."""
        with pytest.raises(ValueError, match="256 bits"):
            EncryptionConfig(key=b"short")

    def test_missing_key_validation(self):
        """Test that missing key fails validation."""
        config = EncryptionConfig()
        with pytest.raises(ValueError, match="required"):
            config.validate()

    def test_default_algorithm(self):
        """Test default algorithm is AES-256-GCM."""
        config = EncryptionConfig()
        assert config.algorithm == EncryptionAlgorithm.AES_256_GCM


class TestKeyManagement:
    """Test key management utilities."""

    def test_generate_key(self):
        """Test key generation."""
        key = generate_key()
        assert len(key) == 32
        assert isinstance(key, bytes)

    def test_generate_key_unique(self):
        """Test that generated keys are unique."""
        key1 = generate_key()
        key2 = generate_key()
        assert key1 != key2

    def test_secure_key_storage(self):
        """Test SecureKeyStorage get_key."""
        key = generate_key()
        storage = SecureKeyStorage(key)
        assert storage.get_key() == key

    def test_secure_key_storage_clear(self):
        """Test SecureKeyStorage clear."""
        key = generate_key()
        storage = SecureKeyStorage(key)
        storage.clear()
        # After clear, the internal bytearray should be zeroed
        assert all(b == 0 for b in storage._key)

    def test_secure_key_storage_context_manager(self):
        """Test SecureKeyStorage as context manager."""
        key = generate_key()
        with SecureKeyStorage(key) as storage:
            assert storage.get_key() == key
        # After exit, key should be cleared
        assert all(b == 0 for b in storage._key)

    def test_key_to_from_base64(self):
        """Test base64 encoding/decoding."""
        key = generate_key()
        encoded = key_to_base64(key)
        decoded = key_from_base64(encoded)
        assert decoded == key

    def test_load_key_from_env(self):
        """Test loading key from environment variable."""
        key = generate_key()
        env_var = "TEST_LOG_ENCRYPTION_KEY"
        os.environ[env_var] = key_to_base64(key)
        try:
            loaded = load_key_from_env(env_var)
            assert loaded == key
        finally:
            del os.environ[env_var]

    def test_load_key_from_env_missing(self):
        """Test loading key from missing environment variable."""
        with pytest.raises(ValueError, match="not found"):
            load_key_from_env("NONEXISTENT_VAR")

    def test_save_and_load_key_from_file(self):
        """Test saving and loading key from file."""
        key = generate_key()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = f.name

        try:
            save_key_to_file(key, filepath)
            loaded = load_key_from_file(filepath)
            assert loaded == key
        finally:
            os.unlink(filepath)


class TestEncryptedWriter:
    """Test encrypted writer functionality."""

    def test_encrypt_decrypt_aes_gcm(self):
        """Test encryption and decryption with AES-256-GCM."""
        key = generate_key()
        config = EncryptionConfig(key=key, algorithm=EncryptionAlgorithm.AES_256_GCM)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            # Create writer and write log
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            entry = LogEntry(level=LogLevel.INFO, message="Test message")
            encrypted_writer.write(entry)
            encrypted_writer.flush()
            encrypted_writer.close()

            # Read and decrypt
            decryptor = LogDecryptor(key, EncryptionAlgorithm.AES_256_GCM)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 1
            assert "Test message" in decrypted[0]
        finally:
            os.unlink(filepath)

    def test_encrypt_decrypt_aes_cbc(self):
        """Test encryption and decryption with AES-256-CBC."""
        key = generate_key()
        config = EncryptionConfig(key=key, algorithm=EncryptionAlgorithm.AES_256_CBC)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            entry = LogEntry(level=LogLevel.INFO, message="Test CBC message")
            encrypted_writer.write(entry)
            encrypted_writer.flush()
            encrypted_writer.close()

            decryptor = LogDecryptor(key, EncryptionAlgorithm.AES_256_CBC)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 1
            assert "Test CBC message" in decrypted[0]
        finally:
            os.unlink(filepath)

    def test_encrypt_decrypt_chacha20(self):
        """Test encryption and decryption with ChaCha20-Poly1305."""
        key = generate_key()
        config = EncryptionConfig(key=key, algorithm=EncryptionAlgorithm.CHACHA20_POLY1305)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            entry = LogEntry(level=LogLevel.INFO, message="Test ChaCha20 message")
            encrypted_writer.write(entry)
            encrypted_writer.flush()
            encrypted_writer.close()

            decryptor = LogDecryptor(key, EncryptionAlgorithm.CHACHA20_POLY1305)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 1
            assert "Test ChaCha20 message" in decrypted[0]
        finally:
            os.unlink(filepath)

    def test_multiple_entries(self):
        """Test encrypting multiple log entries."""
        key = generate_key()
        config = EncryptionConfig(key=key)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            messages = ["First message", "Second message", "Third message"]
            for msg in messages:
                entry = LogEntry(level=LogLevel.INFO, message=msg)
                encrypted_writer.write(entry)

            encrypted_writer.flush()
            encrypted_writer.close()

            decryptor = LogDecryptor(key)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 3
            for msg, decrypted_line in zip(messages, decrypted):
                assert msg in decrypted_line
        finally:
            os.unlink(filepath)

    def test_unique_iv_per_entry(self):
        """Test that each entry uses unique IV."""
        key = generate_key()
        config = EncryptionConfig(key=key, rotate_iv=True)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            # Write same message twice
            for _ in range(2):
                entry = LogEntry(level=LogLevel.INFO, message="Same message")
                encrypted_writer.write(entry)

            encrypted_writer.flush()
            encrypted_writer.close()

            # Read encrypted content - should be different
            with open(filepath, 'r') as f:
                lines = f.readlines()

            assert len(lines) == 2
            # Encrypted data should be different due to unique IVs
            assert lines[0] != lines[1]
        finally:
            os.unlink(filepath)


class TestLogDecryptor:
    """Test log decryptor functionality."""

    def test_decrypt_to_file(self):
        """Test decrypting to output file."""
        key = generate_key()
        config = EncryptionConfig(key=key)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            encrypted_path = f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            decrypted_path = f.name

        try:
            file_writer = FileWriter(encrypted_path)
            encrypted_writer = EncryptedWriter(file_writer, config)

            entry = LogEntry(level=LogLevel.INFO, message="Message to decrypt")
            encrypted_writer.write(entry)
            encrypted_writer.flush()
            encrypted_writer.close()

            decryptor = LogDecryptor(key)
            count = decryptor.decrypt_to_file(encrypted_path, decrypted_path)

            assert count == 1

            with open(decrypted_path, 'r') as f:
                content = f.read()
                assert "Message to decrypt" in content
        finally:
            os.unlink(encrypted_path)
            os.unlink(decrypted_path)

    def test_decrypt_with_skip_errors(self):
        """Test decryption with skip_errors flag."""
        key = generate_key()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            f.write("invalid_base64_data\n")
            f.write("also_invalid\n")
            filepath = f.name

        try:
            decryptor = LogDecryptor(key)
            result = decryptor.decrypt_file(filepath, skip_errors=True)

            assert len(result) == 2
            assert all("DECRYPTION_ERROR" in line for line in result)
        finally:
            os.unlink(filepath)

    def test_decrypt_iterator(self):
        """Test decrypt_file_iter for lazy decryption."""
        key = generate_key()
        config = EncryptionConfig(key=key)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            file_writer = FileWriter(filepath)
            encrypted_writer = EncryptedWriter(file_writer, config)

            for i in range(5):
                entry = LogEntry(level=LogLevel.INFO, message=f"Message {i}")
                encrypted_writer.write(entry)

            encrypted_writer.flush()
            encrypted_writer.close()

            decryptor = LogDecryptor(key)
            count = 0
            for line in decryptor.decrypt_file_iter(filepath):
                assert f"Message {count}" in line
                count += 1

            assert count == 5
        finally:
            os.unlink(filepath)


class TestLoggerBuilderIntegration:
    """Test integration with LoggerBuilder."""

    def test_builder_with_encryption(self):
        """Test LoggerBuilder with_encryption method."""
        key = generate_key()
        config = EncryptionConfig(key=key)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log.enc', delete=False) as f:
            filepath = f.name

        try:
            logger = (LoggerBuilder()
                .with_name("test-encrypted")
                .with_file(filepath)
                .with_encryption(config)
                .build())

            logger.info("Encrypted via builder")
            logger.flush()
            logger.shutdown()

            decryptor = LogDecryptor(key)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 1
            assert "Encrypted via builder" in decrypted[0]
        finally:
            os.unlink(filepath)

    def test_builder_encryption_with_rotating_file(self):
        """Test encryption with rotating file writer."""
        key = generate_key()
        config = EncryptionConfig(key=key)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "rotating.log.enc")

            logger = (LoggerBuilder()
                .with_name("test-rotating-encrypted")
                .with_file(filepath, rotating=True)
                .with_encryption(config)
                .build())

            logger.info("Encrypted rotating log")
            logger.flush()
            logger.shutdown()

            decryptor = LogDecryptor(key)
            decrypted = decryptor.decrypt_file(filepath)

            assert len(decrypted) == 1
            assert "Encrypted rotating log" in decrypted[0]
