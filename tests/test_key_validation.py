"""Key validation tests."""

from __future__ import annotations

import base64

import pytest

from security.exceptions import (
    InvalidEncryptionKeyError,
    InvalidFingerprintKeyError,
    MissingEncryptionKeyError,
    SameKeyError,
)
from security.key_validation import (
    generate_encryption_key,
    generate_fingerprint_key,
    load_encryption_key,
    load_fingerprint_key,
    load_keys,
)


class TestKeyValidation:
    def test_valid_encryption_key_accepted(self) -> None:
        key = generate_encryption_key()
        ek = load_encryption_key(key)
        assert len(ek.key_bytes) == 32

    def test_valid_fingerprint_key_accepted(self) -> None:
        key = generate_fingerprint_key()
        fk = load_fingerprint_key(key)
        assert len(fk.key_bytes) >= 32

    def test_missing_encryption_key_rejected(self) -> None:
        with pytest.raises(MissingEncryptionKeyError):
            load_encryption_key(None)

    def test_missing_encryption_key_empty_rejected(self) -> None:
        with pytest.raises(MissingEncryptionKeyError):
            load_encryption_key("")

    def test_wrong_encryption_key_length_rejected(self) -> None:
        short = base64.urlsafe_b64encode(b"short").decode()
        with pytest.raises(InvalidEncryptionKeyError):
            load_encryption_key(short)

    def test_wrong_fingerprint_key_length_rejected(self) -> None:
        short = base64.urlsafe_b64encode(b"short").decode()
        with pytest.raises(InvalidFingerprintKeyError):
            load_fingerprint_key(short)

    def test_same_encryption_and_fingerprint_key_rejected(self) -> None:
        key = generate_encryption_key()
        with pytest.raises(SameKeyError):
            load_keys(key, key)

    def test_load_keys_success(self) -> None:
        ek = generate_encryption_key()
        fk = generate_fingerprint_key()
        enc_key, fp_key = load_keys(ek, fk)
        assert enc_key.key_bytes != fp_key.key_bytes

    def test_key_repr_does_not_expose_value(self) -> None:
        ek = load_encryption_key(generate_encryption_key())
        assert "EncryptionKey" in repr(ek)
        assert ek.key_bytes.hex() not in repr(ek)
