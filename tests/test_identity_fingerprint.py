"""HMAC-SHA256 fingerprint tests."""

from __future__ import annotations

import pytest

from security.fingerprint import (
    fingerprint_email,
    fingerprint_institutional_id,
    normalize_email,
    normalize_student_id,
)
from security.key_validation import generate_fingerprint_key, load_fingerprint_key
from security.models import FingerprintKey


@pytest.fixture
def fp_key() -> FingerprintKey:
    return load_fingerprint_key(generate_fingerprint_key())


class TestFingerprint:
    def test_deterministic(self, fp_key) -> None:
        fp1 = fingerprint_email("test@example.com", fp_key)
        fp2 = fingerprint_email("test@example.com", fp_key)
        assert fp1 == fp2

    def test_different_values_different_fingerprints(self, fp_key) -> None:
        fp1 = fingerprint_email("a@example.com", fp_key)
        fp2 = fingerprint_email("b@example.com", fp_key)
        assert fp1 != fp2

    def test_email_case_normalized(self, fp_key) -> None:
        fp1 = fingerprint_email("Test@Example.com", fp_key)
        fp2 = fingerprint_email("test@example.com", fp_key)
        assert fp1 == fp2

    def test_email_whitespace_normalized(self, fp_key) -> None:
        fp1 = fingerprint_email(" test@example.com ", fp_key)
        fp2 = fingerprint_email("test@example.com", fp_key)
        assert fp1 == fp2

    def test_student_id_leading_zeros_preserved(self, fp_key) -> None:
        fp1 = fingerprint_institutional_id("00123", fp_key)
        fp2 = fingerprint_institutional_id("123", fp_key)
        assert fp1 != fp2

    def test_domain_separation(self, fp_key) -> None:
        same_value = "student@example.com"
        fp_email = fingerprint_email(same_value, fp_key)
        fp_id = fingerprint_institutional_id(same_value, fp_key)
        assert fp_email != fp_id

    def test_different_keys_different_fingerprints(self) -> None:
        k1 = load_fingerprint_key(generate_fingerprint_key())
        k2 = load_fingerprint_key(generate_fingerprint_key())
        fp1 = fingerprint_email("test@example.com", k1)
        fp2 = fingerprint_email("test@example.com", k2)
        assert fp1 != fp2

    def test_none_returns_none(self, fp_key) -> None:
        assert fingerprint_email(None, fp_key) is None
        assert fingerprint_institutional_id(None, fp_key) is None

    def test_normalize_email(self) -> None:
        assert normalize_email(" Test@Example.COM ") == "test@example.com"

    def test_normalize_student_id(self) -> None:
        assert normalize_student_id(" 00123 ") == "00123"
