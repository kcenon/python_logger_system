"""Encrypted writer for secure log storage"""

import os
import base64
from typing import Optional

from logger_module.core.log_entry import LogEntry
from logger_module.security.encryption_config import (
    EncryptionConfig,
    EncryptionAlgorithm,
)


class EncryptedWriter:
    """
    Writer that encrypts log entries before writing.

    Uses decorator pattern to wrap any inner writer with encryption.
    Supports AES-256-GCM, AES-256-CBC, and ChaCha20-Poly1305.
    """

    # IV sizes for different algorithms
    IV_SIZES = {
        EncryptionAlgorithm.AES_256_GCM: 12,  # 96 bits for GCM
        EncryptionAlgorithm.AES_256_CBC: 16,  # 128 bits for CBC
        EncryptionAlgorithm.CHACHA20_POLY1305: 12,  # 96 bits for ChaCha20
    }

    def __init__(
        self,
        inner_writer,
        config: EncryptionConfig,
        formatter=None,
    ):
        """
        Initialize encrypted writer.

        Args:
            inner_writer: Writer to wrap (FileWriter, RotatingFileWriter, etc.)
            config: Encryption configuration
            formatter: Optional log formatter
        """
        config.validate()

        self.inner_writer = inner_writer
        self.config = config
        self.formatter = formatter
        self._cipher = self._create_cipher()

    def _create_cipher(self):
        """Create cipher based on algorithm."""
        try:
            if self.config.algorithm == EncryptionAlgorithm.AES_256_GCM:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                return AESGCM(self.config.key)

            elif self.config.algorithm == EncryptionAlgorithm.AES_256_CBC:
                # CBC mode needs different handling (non-AEAD)
                return None  # Will use _encrypt_cbc method

            elif self.config.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                return ChaCha20Poly1305(self.config.key)

        except ImportError as e:
            raise ImportError(
                "cryptography library is required for encryption. "
                "Install with: pip install cryptography"
            ) from e

    def _generate_iv(self) -> bytes:
        """Generate initialization vector."""
        iv_size = self.IV_SIZES.get(self.config.algorithm, 12)
        return os.urandom(iv_size)

    def _encrypt_gcm(self, plaintext: bytes, iv: bytes) -> bytes:
        """Encrypt using AES-256-GCM."""
        return self._cipher.encrypt(iv, plaintext, None)

    def _encrypt_cbc(self, plaintext: bytes, iv: bytes) -> bytes:
        """Encrypt using AES-256-CBC with PKCS7 padding."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.backends import default_backend

        # Apply PKCS7 padding
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()

        # Encrypt
        cipher = Cipher(
            algorithms.AES(self.config.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        return encryptor.update(padded_data) + encryptor.finalize()

    def _encrypt_chacha(self, plaintext: bytes, iv: bytes) -> bytes:
        """Encrypt using ChaCha20-Poly1305."""
        return self._cipher.encrypt(iv, plaintext, None)

    def _encrypt(self, plaintext: bytes) -> str:
        """
        Encrypt plaintext and return base64-encoded result.

        Format: base64(iv + ciphertext)

        Args:
            plaintext: Data to encrypt

        Returns:
            Base64-encoded encrypted data
        """
        iv = self._generate_iv()

        if self.config.algorithm == EncryptionAlgorithm.AES_256_GCM:
            ciphertext = self._encrypt_gcm(plaintext, iv)
        elif self.config.algorithm == EncryptionAlgorithm.AES_256_CBC:
            ciphertext = self._encrypt_cbc(plaintext, iv)
        elif self.config.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
            ciphertext = self._encrypt_chacha(plaintext, iv)
        else:
            raise ValueError(f"Unsupported algorithm: {self.config.algorithm}")

        # Combine IV and ciphertext, then base64 encode
        return base64.b64encode(iv + ciphertext).decode("ascii")

    def write(self, entry: LogEntry) -> None:
        """
        Encrypt and write log entry.

        Args:
            entry: Log entry to write
        """
        # Format entry
        if self.formatter:
            plaintext = self.formatter.format(entry)
        else:
            plaintext = str(entry)

        # Encrypt
        encrypted_data = self._encrypt(plaintext.encode("utf-8"))

        # Create encrypted entry (preserving metadata for filtering)
        encrypted_entry = LogEntry(
            level=entry.level,
            message=encrypted_data,
            timestamp=entry.timestamp,
            thread_id=entry.thread_id,
            thread_name=entry.thread_name,
            logger_name=entry.logger_name,
            extra={"_encrypted": True, "_algorithm": self.config.algorithm.value},
        )

        # Write to inner writer
        self.inner_writer.write(encrypted_entry)

    def flush(self) -> None:
        """Flush inner writer."""
        if hasattr(self.inner_writer, "flush"):
            self.inner_writer.flush()

    def close(self) -> None:
        """Close inner writer."""
        if hasattr(self.inner_writer, "close"):
            self.inner_writer.close()
