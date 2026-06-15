"""Encryption/decryption round-trip tests."""

from __future__ import annotations

import pytest

from security.encryption import decrypt_text, encrypt_text
from security.key_validation import generate_encryption_key, load_encryption_key
from security.models import EncryptionKey


@pytest.fixture
def enc_key() -> EncryptionKey:
    return load_encryption_key(generate_encryption_key())


class TestEncryption:
    def test_round_trip(self, enc_key) -> None:
        original = "Hello, World!"
        encrypted = encrypt_text(enc_key, original)
        assert encrypted is not None
        assert encrypted != original
        decrypted = decrypt_text(enc_key, encrypted)
        assert decrypted == original

    def test_same_plaintext_different_ciphertext(self, enc_key) -> None:
        text = "Same text"
        c1 = encrypt_text(enc_key, text)
        c2 = encrypt_text(enc_key, text)
        assert c1 != c2

    def test_wrong_key_fails(self, enc_key) -> None:
        encrypted = encrypt_text(enc_key, "Secret")
        wrong_key = load_encryption_key(generate_encryption_key())
        with pytest.raises(Exception):
            decrypt_text(wrong_key, encrypted)

    def test_tampered_ciphertext_fails(self, enc_key) -> None:
        encrypted = encrypt_text(enc_key, "Secret")
        assert encrypted is not None
        tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
        with pytest.raises(Exception):
            decrypt_text(enc_key, tampered)

    def test_none_round_trip(self, enc_key) -> None:
        assert encrypt_text(enc_key, None) is None
        assert decrypt_text(enc_key, None) is None

    def test_empty_string(self, enc_key) -> None:
        encrypted = encrypt_text(enc_key, "")
        assert encrypted is not None
        decrypted = decrypt_text(enc_key, encrypted)
        assert decrypted == ""

    def test_unicode_round_trip(self, enc_key) -> None:
        original = "مرحبا بالعالم"
        encrypted = encrypt_text(enc_key, original)
        decrypted = decrypt_text(enc_key, encrypted)
        assert decrypted == original

    def test_long_text_round_trip(self, enc_key) -> None:
        original = "A" * 10_000
        encrypted = encrypt_text(enc_key, original)
        decrypted = decrypt_text(enc_key, encrypted)
        assert decrypted == original

    def test_ciphertext_does_not_contain_plaintext(self, enc_key) -> None:
        original = "SecretValue123!"
        encrypted = encrypt_text(enc_key, original)
        assert encrypted is not None
        assert original not in encrypted
