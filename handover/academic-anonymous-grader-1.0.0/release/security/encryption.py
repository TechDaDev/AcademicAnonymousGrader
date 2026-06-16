"""AES-256-GCM identity field encryption with versioned envelope."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from security.exceptions import (
    IdentityDecryptionError,
    IdentityEncryptionError,
    UnsupportedCiphertextVersionError,
)
from security.models import CiphertextEnvelope, EncryptionKey

_NONCE_LENGTH = 12
_ENCODED_ENVELOPE_VERSION = 1


def _encrypt(key: EncryptionKey, plaintext: str) -> str:
    """Encrypt plaintext with AES-256-GCM and return URL-safe base64 envelope."""
    if not isinstance(plaintext, str):
        raise IdentityEncryptionError("Plaintext must be a string")
    data = plaintext.encode("utf-8")
    nonce = os.urandom(_NONCE_LENGTH)
    try:
        aesgcm = AESGCM(key.key_bytes)
        ciphertext = aesgcm.encrypt(nonce, data, None)
    except Exception as exc:
        raise IdentityEncryptionError("Encryption failed") from exc
    envelope = CiphertextEnvelope(_ENCODED_ENVELOPE_VERSION, nonce, ciphertext)
    return _encode_envelope(envelope)


def _decrypt(key: EncryptionKey, encoded: str) -> str:
    """Decrypt a URL-safe base64 envelope and return plaintext UTF-8 string."""
    try:
        envelope = _decode_envelope(encoded)
    except Exception as exc:
        raise IdentityDecryptionError("Failed to decode ciphertext envelope") from exc
    if envelope.version != _ENCODED_ENVELOPE_VERSION:
        raise UnsupportedCiphertextVersionError(
            f"Unsupported ciphertext version {envelope.version}"
        )
    try:
        aesgcm = AESGCM(key.key_bytes)
        plaintext_bytes = aesgcm.decrypt(envelope.nonce, envelope.ciphertext, None)
    except Exception as exc:
        raise IdentityDecryptionError("Decryption failed — wrong key or tampered data") from exc
    return plaintext_bytes.decode("utf-8")


def _encode_envelope(envelope: CiphertextEnvelope) -> str:
    """Encode envelope to URL-safe base64 string."""
    raw = bytes([envelope.version]) + envelope.nonce + envelope.ciphertext
    return base64.urlsafe_b64encode(raw).decode()


def _decode_envelope(encoded: str) -> CiphertextEnvelope:
    """Decode URL-safe base64 string into CiphertextEnvelope."""
    raw = base64.urlsafe_b64decode(encoded)
    if len(raw) < 1 + _NONCE_LENGTH + 1:
        raise ValueError("Ciphertext too short")
    version = raw[0]
    nonce = raw[1:1 + _NONCE_LENGTH]
    ciphertext = raw[1 + _NONCE_LENGTH:]
    return CiphertextEnvelope(version, nonce, ciphertext)


def encrypt_text(key: EncryptionKey, plaintext: str | None) -> str | None:
    """Encrypt a required text field. Returns None if input is None."""
    if plaintext is None:
        return None
    if not plaintext:
        return _encrypt(key, "")
    return _encrypt(key, plaintext)


def decrypt_text(key: EncryptionKey, ciphertext: str | None) -> str | None:
    """Decrypt a text field. Returns None if input is None."""
    if ciphertext is None:
        return None
    return _decrypt(key, ciphertext)
