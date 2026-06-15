"""Key material and ciphertext envelope models."""

from __future__ import annotations


class EncryptionKey:
    """Holds a validated 32-byte AES-GCM encryption key."""

    __slots__ = ("key_bytes",)

    def __init__(self, key_bytes: bytes) -> None:
        if len(key_bytes) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes")
        self.key_bytes = key_bytes

    def __repr__(self) -> str:
        return "<EncryptionKey>"


class FingerprintKey:
    """Holds a validated HMAC-SHA256 fingerprint key (minimum 32 bytes)."""

    __slots__ = ("key_bytes",)

    def __init__(self, key_bytes: bytes) -> None:
        if len(key_bytes) < 32:
            raise ValueError("Fingerprint key must be at least 32 bytes")
        self.key_bytes = key_bytes

    def __repr__(self) -> str:
        return "<FingerprintKey>"


class CiphertextEnvelope:
    """Versioned ciphertext envelope: version || nonce || ciphertext."""

    __slots__ = ("version", "nonce", "ciphertext")

    CURRENT_VERSION = 1

    def __init__(self, version: int, nonce: bytes, ciphertext: bytes) -> None:
        self.version = version
        self.nonce = nonce
        self.ciphertext = ciphertext

    def __repr__(self) -> str:
        return f"<CiphertextEnvelope version={self.version} nonce_len={len(self.nonce)} ct_len={len(self.ciphertext)}>"
