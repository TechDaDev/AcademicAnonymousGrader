"""Encryption-related exceptions."""

from __future__ import annotations


class SecurityError(Exception):
    """Base security exception."""


class MissingEncryptionKeyError(SecurityError):
    """Raised when IDENTITY_ENCRYPTION_KEY is not set."""


class InvalidEncryptionKeyError(SecurityError):
    """Raised when IDENTITY_ENCRYPTION_KEY has invalid format or length."""


class MissingFingerprintKeyError(SecurityError):
    """Raised when IDENTITY_FINGERPRINT_KEY is not set."""


class InvalidFingerprintKeyError(SecurityError):
    """Raised when IDENTITY_FINGERPRINT_KEY has invalid format or length."""


class IdentityEncryptionError(SecurityError):
    """Raised when encryption of identity data fails."""


class IdentityDecryptionError(SecurityError):
    """Raised when decryption of identity data fails."""


class UnsupportedCiphertextVersionError(SecurityError):
    """Raised when ciphertext has an unknown version byte."""


class SameKeyError(SecurityError):
    """Raised when encryption and fingerprint keys are identical."""


class InvalidAnonymousCodeError(SecurityError):
    """Raised when an anonymous ID format is invalid."""


class AnonymousCodeCollisionError(SecurityError):
    """Raised when generated anonymous ID collides with existing one."""
