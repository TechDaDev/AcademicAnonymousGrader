"""Identity matching service tests — deterministic hierarchy."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from models.student_identity import StudentIdentity
from security.encryption import encrypt_text
from security.fingerprint import (
    fingerprint_email,
    fingerprint_institutional_id,
)
from security.key_validation import (
    generate_encryption_key,
    generate_fingerprint_key,
    load_encryption_key,
    load_fingerprint_key,
)
from services.identity_matching_service import (
    MatchResultType,
    _mask_email,
    _mask_id,
    _mask_text,
    find_matching_identity,
)


@pytest.fixture
def fp_key() -> object:
    return load_fingerprint_key(generate_fingerprint_key())


@pytest.fixture
def enc_key() -> object:
    return load_encryption_key(generate_encryption_key())


class TestFindMatchingIdentity:
    def test_match_by_institutional_id(self, session: Session, fp_key, enc_key) -> None:
        """Match by institutional-ID fingerprint."""
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Alice"),
            encrypted_email=encrypt_text(enc_key, "alice@example.com"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID001"),
            email_fingerprint=fingerprint_email("alice@example.com", fp_key),
            institutional_id_fingerprint=fingerprint_institutional_id("ID001", fp_key),
        )
        session.add(identity)
        session.flush()

        result = find_matching_identity(session, "ID001", None, fp_key)
        assert result.result_type == MatchResultType.MATCHED_BY_INSTITUTIONAL_ID
        assert result.existing_identity_id == identity.id
        assert result.blocking is False

    def test_match_by_email(self, session: Session, fp_key, enc_key) -> None:
        """Match by email fingerprint when no institutional ID provided."""
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Bob"),
            encrypted_email=encrypt_text(enc_key, "bob@example.com"),
            email_fingerprint=fingerprint_email("bob@example.com", fp_key),
        )
        session.add(identity)
        session.flush()

        result = find_matching_identity(session, None, "bob@example.com", fp_key)
        assert result.result_type == MatchResultType.MATCHED_BY_EMAIL
        assert result.existing_identity_id == identity.id
        assert result.blocking is False

    def test_institutional_id_takes_precedence(self, session: Session, fp_key, enc_key) -> None:
        """ID match takes precedence over email match when both exist."""
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Charlie"),
            encrypted_email=encrypt_text(enc_key, "charlie@example.com"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID002"),
            email_fingerprint=fingerprint_email("charlie@example.com", fp_key),
            institutional_id_fingerprint=fingerprint_institutional_id("ID002", fp_key),
        )
        session.add(identity)
        session.flush()

        result = find_matching_identity(session, "ID002", "charlie@example.com", fp_key)
        assert result.result_type == MatchResultType.MATCHED_BY_INSTITUTIONAL_ID
        assert result.existing_identity_id == identity.id

    def test_new_identity(self, session: Session, fp_key) -> None:
        """No match creates new identity."""
        result = find_matching_identity(session, "NEW-ID", "new@example.com", fp_key)
        assert result.result_type == MatchResultType.NEW_IDENTITY
        assert result.existing_identity_id is None
        assert result.blocking is False

    def test_ambiguous_conflict(self, session: Session, fp_key, enc_key) -> None:
        """Conflicting ID/email matches produce ambiguity."""
        identity1 = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "David"),
            encrypted_institutional_student_id=encrypt_text(enc_key, "ID003"),
            institutional_id_fingerprint=fingerprint_institutional_id("ID003", fp_key),
        )
        identity2 = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Eve"),
            encrypted_email=encrypt_text(enc_key, "eve@example.com"),
            email_fingerprint=fingerprint_email("eve@example.com", fp_key),
        )
        session.add_all([identity1, identity2])
        session.flush()

        result = find_matching_identity(session, "ID003", "eve@example.com", fp_key)
        assert result.result_type == MatchResultType.AMBIGUOUS_CONFLICT
        assert result.blocking is True

    def test_names_never_auto_match(self, session: Session, fp_key) -> None:
        """Names alone never trigger auto-match."""
        # Without ID or email, should be MANUAL_RESOLUTION_REQUIRED
        result = find_matching_identity(session, None, None, fp_key)
        assert result.result_type == MatchResultType.MANUAL_RESOLUTION_REQUIRED
        assert result.blocking is True

    def test_missing_email_and_id_requires_manual(self, session: Session, fp_key) -> None:
        """Missing email and ID requires manual resolution."""
        result = find_matching_identity(session, None, None, fp_key)
        assert result.result_type == MatchResultType.MANUAL_RESOLUTION_REQUIRED
        assert result.blocking is True

    def test_normalized_email_matches(self, session: Session, fp_key, enc_key) -> None:
        """Normalized version of email should match fingerprint."""
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Frank"),
            encrypted_email=encrypt_text(enc_key, "frank@example.com"),
            email_fingerprint=fingerprint_email("frank@example.com", fp_key),
        )
        session.add(identity)
        session.flush()

        result = find_matching_identity(session, None, "Frank@Example.COM", fp_key)
        assert result.result_type == MatchResultType.MATCHED_BY_EMAIL

    def test_different_key_different_match(self, session: Session, fp_key, enc_key) -> None:
        """Different fingerprint key produces different match results."""
        identity = StudentIdentity(
            encrypted_first_name=encrypt_text(enc_key, "Grace"),
            encrypted_email=encrypt_text(enc_key, "grace@example.com"),
            email_fingerprint=fingerprint_email("grace@example.com", fp_key),
        )
        session.add(identity)
        session.flush()

        # With current key should match
        result1 = find_matching_identity(session, None, "grace@example.com", fp_key)
        assert result1.result_type == MatchResultType.MATCHED_BY_EMAIL

        # With different key, fingerprint won't match
        other_fp_key = load_fingerprint_key(generate_fingerprint_key())
        result2 = find_matching_identity(session, None, "grace@example.com", other_fp_key)
        assert result2.result_type == MatchResultType.NEW_IDENTITY


class TestMaskingHelpers:
    def test_mask_text_short(self) -> None:
        assert _mask_text("AB") == "A*"

    def test_mask_text_long(self) -> None:
        assert _mask_text("Hello") == "H***o"

    def test_mask_text_none(self) -> None:
        assert _mask_text(None) == ""

    def test_mask_email(self) -> None:
        masked = _mask_email("john.doe@example.com")
        assert masked == "j******e@example.com"

    def test_mask_email_none(self) -> None:
        assert _mask_email(None) == ""

    def test_mask_id(self) -> None:
        masked = _mask_id("S1234567")
        assert len(masked) == 8
        assert masked.startswith("S1")
        assert masked.endswith("67")

    def test_mask_id_short(self) -> None:
        assert _mask_id("AB") == "**"

    def test_mask_id_none(self) -> None:
        assert _mask_id(None) == ""
