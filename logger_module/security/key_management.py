"""Key management utilities for secure logging"""

import os
import base64
from typing import Optional


class SecureKeyStorage:
    """
    Secure key storage with RAII-style cleanup.

    Stores encryption key in memory and securely zeros it on deletion.
    """

    def __init__(self, key: bytes):
        """
        Initialize secure key storage.

        Args:
            key: Encryption key (must be 32 bytes for AES-256)
        """
        if len(key) != 32:
            raise ValueError("Key must be 256 bits (32 bytes)")
        self._key = bytearray(key)

    def get_key(self) -> bytes:
        """
        Get the encryption key.

        Returns:
            The encryption key as bytes
        """
        return bytes(self._key)

    def clear(self) -> None:
        """Securely zero out the key material."""
        for i in range(len(self._key)):
            self._key[i] = 0

    def __del__(self):
        """Securely zero out key material on deletion."""
        self.clear()

    def __enter__(self) -> "SecureKeyStorage":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - clears key."""
        self.clear()


def generate_key() -> bytes:
    """
    Generate a new 256-bit encryption key.

    Returns:
        32 bytes of cryptographically secure random data
    """
    return os.urandom(32)


def load_key_from_env(env_var: str = "LOG_ENCRYPTION_KEY") -> bytes:
    """
    Load encryption key from environment variable.

    The key should be base64-encoded in the environment variable.

    Args:
        env_var: Name of environment variable

    Returns:
        The decoded encryption key

    Raises:
        ValueError: If environment variable not found or invalid
    """
    key_b64 = os.environ.get(env_var)
    if not key_b64:
        raise ValueError(f"Encryption key not found in environment variable: {env_var}")

    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64-encoded key in {env_var}") from e

    if len(key) != 32:
        raise ValueError(
            f"Key from {env_var} must be 256 bits (32 bytes), got {len(key)} bytes"
        )

    return key


def load_key_from_file(filepath: str) -> bytes:
    """
    Load encryption key from file.

    The file should contain a base64-encoded key.

    Args:
        filepath: Path to key file

    Returns:
        The decoded encryption key

    Raises:
        ValueError: If file not found or key invalid
        FileNotFoundError: If file doesn't exist
    """
    with open(filepath, "r") as f:
        key_b64 = f.read().strip()

    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64-encoded key in {filepath}") from e

    if len(key) != 32:
        raise ValueError(
            f"Key from {filepath} must be 256 bits (32 bytes), got {len(key)} bytes"
        )

    return key


def save_key_to_file(key: bytes, filepath: str, mode: int = 0o600) -> None:
    """
    Save encryption key to file with secure permissions.

    Args:
        key: Encryption key to save
        filepath: Path to key file
        mode: File permissions (default: 0o600 - owner read/write only)
    """
    if len(key) != 32:
        raise ValueError("Key must be 256 bits (32 bytes)")

    key_b64 = base64.b64encode(key).decode("ascii")

    # Create file with secure permissions
    fd = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, key_b64.encode("ascii"))
    finally:
        os.close(fd)


def key_to_base64(key: bytes) -> str:
    """
    Encode key as base64 string.

    Args:
        key: Encryption key

    Returns:
        Base64-encoded key string
    """
    return base64.b64encode(key).decode("ascii")


def key_from_base64(key_b64: str) -> bytes:
    """
    Decode key from base64 string.

    Args:
        key_b64: Base64-encoded key

    Returns:
        Decoded key bytes
    """
    return base64.b64decode(key_b64)
