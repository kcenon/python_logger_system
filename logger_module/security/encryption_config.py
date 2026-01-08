"""Encryption configuration for secure logging"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""

    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"


@dataclass
class EncryptionConfig:
    """
    Configuration for log encryption.

    Attributes:
        algorithm: Encryption algorithm to use
        key: 256-bit encryption key
        rotate_iv: Whether to use unique IV per entry (recommended)
        key_rotation_hours: Hours between key rotations (optional)
    """

    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM
    key: Optional[bytes] = None
    rotate_iv: bool = True
    key_rotation_hours: Optional[int] = None

    def __post_init__(self):
        """Validate configuration."""
        if self.key is not None:
            if len(self.key) != 32:
                raise ValueError("Encryption key must be 256 bits (32 bytes)")

    def validate(self) -> None:
        """
        Validate that configuration is complete.

        Raises:
            ValueError: If key is missing or invalid
        """
        if self.key is None:
            raise ValueError("Encryption key is required")
        if len(self.key) != 32:
            raise ValueError("Encryption key must be 256 bits (32 bytes)")
