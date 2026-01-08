"""Log decryption utility for reading encrypted logs"""

import base64
from typing import List, Iterator, Optional
from pathlib import Path

from logger_module.security.encryption_config import EncryptionAlgorithm


class LogDecryptor:
    """
    Utility to decrypt encrypted log files.

    Supports all algorithms used by EncryptedWriter.
    """

    # IV sizes for different algorithms
    IV_SIZES = {
        EncryptionAlgorithm.AES_256_GCM: 12,
        EncryptionAlgorithm.AES_256_CBC: 16,
        EncryptionAlgorithm.CHACHA20_POLY1305: 12,
    }

    def __init__(
        self,
        key: bytes,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
    ):
        """
        Initialize decryptor.

        Args:
            key: Encryption key (must match the key used for encryption)
            algorithm: Encryption algorithm used
        """
        if len(key) != 32:
            raise ValueError("Key must be 256 bits (32 bytes)")

        self.key = key
        self.algorithm = algorithm
        self._cipher = self._create_cipher()

    def _create_cipher(self):
        """Create cipher based on algorithm."""
        try:
            if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                return AESGCM(self.key)

            elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
                return None  # Will use _decrypt_cbc method

            elif self.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
                return ChaCha20Poly1305(self.key)

        except ImportError as e:
            raise ImportError(
                "cryptography library is required for decryption. "
                "Install with: pip install cryptography"
            ) from e

    def _decrypt_gcm(self, iv: bytes, ciphertext: bytes) -> bytes:
        """Decrypt using AES-256-GCM."""
        return self._cipher.decrypt(iv, ciphertext, None)

    def _decrypt_cbc(self, iv: bytes, ciphertext: bytes) -> bytes:
        """Decrypt using AES-256-CBC with PKCS7 padding."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.backends import default_backend

        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove PKCS7 padding
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()

    def _decrypt_chacha(self, iv: bytes, ciphertext: bytes) -> bytes:
        """Decrypt using ChaCha20-Poly1305."""
        return self._cipher.decrypt(iv, ciphertext, None)

    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt a single encrypted log entry.

        Args:
            encrypted_data: Base64-encoded encrypted data (iv + ciphertext)

        Returns:
            Decrypted log message

        Raises:
            ValueError: If decryption fails
        """
        try:
            # Decode base64
            data = base64.b64decode(encrypted_data)

            # Split IV and ciphertext
            iv_size = self.IV_SIZES.get(self.algorithm, 12)
            iv = data[:iv_size]
            ciphertext = data[iv_size:]

            # Decrypt based on algorithm
            if self.algorithm == EncryptionAlgorithm.AES_256_GCM:
                plaintext = self._decrypt_gcm(iv, ciphertext)
            elif self.algorithm == EncryptionAlgorithm.AES_256_CBC:
                plaintext = self._decrypt_cbc(iv, ciphertext)
            elif self.algorithm == EncryptionAlgorithm.CHACHA20_POLY1305:
                plaintext = self._decrypt_chacha(iv, ciphertext)
            else:
                raise ValueError(f"Unsupported algorithm: {self.algorithm}")

            return plaintext.decode("utf-8")

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e

    def decrypt_file(self, filepath: str, skip_errors: bool = False) -> List[str]:
        """
        Decrypt an encrypted log file.

        Args:
            filepath: Path to encrypted log file
            skip_errors: If True, skip entries that fail to decrypt

        Returns:
            List of decrypted log messages
        """
        decrypted_lines = []

        for line in self.decrypt_file_iter(filepath, skip_errors):
            decrypted_lines.append(line)

        return decrypted_lines

    def decrypt_file_iter(
        self, filepath: str, skip_errors: bool = False
    ) -> Iterator[str]:
        """
        Decrypt an encrypted log file lazily.

        Args:
            filepath: Path to encrypted log file
            skip_errors: If True, skip entries that fail to decrypt

        Yields:
            Decrypted log messages
        """
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Handle formatted entries: extract the encrypted message
                encrypted_data = self._extract_encrypted_data(line)

                try:
                    yield self.decrypt(encrypted_data)
                except ValueError as e:
                    if skip_errors:
                        yield f"[DECRYPTION_ERROR line {line_num}]: {e}"
                    else:
                        raise

    def _extract_encrypted_data(self, line: str) -> str:
        """
        Extract encrypted data from a formatted log line.

        Log lines may be formatted as:
        - Raw base64: "SGVsbG8gV29ybGQ=..."
        - With prefix: "[2024-01-01] [INFO] SGVsbG8gV29ybGQ=..."

        Args:
            line: Log line to parse

        Returns:
            Extracted base64-encoded encrypted data
        """
        # If the line contains brackets, try to find the message part
        if "] " in line:
            # Find the last ] and take everything after it
            last_bracket = line.rfind("] ")
            if last_bracket != -1:
                return line[last_bracket + 2:].strip()

        return line

    def decrypt_to_file(
        self,
        input_filepath: str,
        output_filepath: str,
        skip_errors: bool = False,
    ) -> int:
        """
        Decrypt an encrypted log file and write to output file.

        Args:
            input_filepath: Path to encrypted log file
            output_filepath: Path to output decrypted file
            skip_errors: If True, skip entries that fail to decrypt

        Returns:
            Number of lines decrypted
        """
        count = 0
        output_path = Path(output_filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_filepath, "w", encoding="utf-8") as out:
            for line in self.decrypt_file_iter(input_filepath, skip_errors):
                out.write(line + "\n")
                count += 1

        return count
