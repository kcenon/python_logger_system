"""
Security module - Encryption and key management for secure logging

Provides:
- EncryptedWriter: Writer that encrypts log data before writing
- LogDecryptor: Utility to decrypt encrypted log files
- Key management utilities for secure key handling

Example:
    from logger_module import LoggerBuilder
    from logger_module.security import (
        EncryptedWriter,
        EncryptionConfig,
        EncryptionAlgorithm,
        generate_key,
        load_key_from_env,
        LogDecryptor,
    )
    from logger_module.writers import FileWriter

    # Generate or load key
    key = generate_key()  # Or load_key_from_env("LOG_ENCRYPTION_KEY")

    # Create encrypted writer
    config = EncryptionConfig(key=key)
    encrypted_writer = EncryptedWriter(
        FileWriter("secure.log.enc"),
        config
    )

    # Use with logger
    logger = (LoggerBuilder()
        .with_name("secure-app")
        .build())
    logger.add_writer(encrypted_writer)

    logger.info("This message will be encrypted")

    # Later, decrypt for analysis
    decryptor = LogDecryptor(key)
    logs = decryptor.decrypt_file("secure.log.enc")
"""

from logger_module.security.encryption_config import (
    EncryptionAlgorithm,
    EncryptionConfig,
)
from logger_module.security.encrypted_writer import EncryptedWriter
from logger_module.security.key_management import (
    SecureKeyStorage,
    generate_key,
    load_key_from_env,
    load_key_from_file,
    save_key_to_file,
    key_to_base64,
    key_from_base64,
)
from logger_module.security.decryptor import LogDecryptor

__all__ = [
    # Configuration
    "EncryptionAlgorithm",
    "EncryptionConfig",
    # Writer
    "EncryptedWriter",
    # Key management
    "SecureKeyStorage",
    "generate_key",
    "load_key_from_env",
    "load_key_from_file",
    "save_key_to_file",
    "key_to_base64",
    "key_from_base64",
    # Decryption
    "LogDecryptor",
]
