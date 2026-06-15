"""Phase 4 security package — encryption, fingerprinting, key validation."""

from security.encryption import decrypt_text, encrypt_text
from security.exceptions import (
    AnonymousCodeCollisionError,
    IdentityDecryptionError,
    IdentityEncryptionError,
    InvalidAnonymousCodeError,
    InvalidEncryptionKeyError,
    InvalidFingerprintKeyError,
    MissingEncryptionKeyError,
    MissingFingerprintKeyError,
    SameKeyError,
    SecurityError,
    UnsupportedCiphertextVersionError,
)
from security.fingerprint import (
    fingerprint_email,
    fingerprint_institutional_id,
    normalize_email,
    normalize_student_id,
)
from security.key_validation import (
    generate_encryption_key,
    generate_fingerprint_key,
    load_encryption_key,
    load_fingerprint_key,
    load_keys,
)
from security.models import CiphertextEnvelope, EncryptionKey, FingerprintKey

__all__ = [
    "AnonymousCodeCollisionError",
    "CiphertextEnvelope",
    "decrypt_text",
    "encrypt_text",
    "EncryptionKey",
    "FingerprintKey",
    "fingerprint_email",
    "fingerprint_institutional_id",
    "generate_encryption_key",
    "generate_fingerprint_key",
    "IdentityDecryptionError",
    "IdentityEncryptionError",
    "InvalidAnonymousCodeError",
    "InvalidEncryptionKeyError",
    "InvalidFingerprintKeyError",
    "load_encryption_key",
    "load_fingerprint_key",
    "load_keys",
    "MissingEncryptionKeyError",
    "MissingFingerprintKeyError",
    "normalize_email",
    "normalize_student_id",
    "SameKeyError",
    "SecurityError",
    "UnsupportedCiphertextVersionError",
]
