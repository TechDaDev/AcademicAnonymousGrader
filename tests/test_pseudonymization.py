"""Pseudonymization service tests — STU-XXXXXXXX code generation."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.student_identity import StudentIdentity
from services.pseudonymization_service import (
    generate_anonymous_code,
    get_or_create_anonymous_student,
    validate_anonymous_code_format,
)


class TestAnonymousCodeFormat:
    def test_stu_prefix(self) -> None:
        code = generate_anonymous_code()
        assert code.startswith("STU-")

    def test_correct_length(self) -> None:
        code = generate_anonymous_code()
        # STU-XXXXXXXX = 4 prefix + 8 chars = 12
        assert len(code) == 12
        suffix = code[4:]
        assert len(suffix) == 8

    def test_allowed_alphabet(self) -> None:
        allowed = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
        for _ in range(100):
            code = generate_anonymous_code()
            suffix = code[4:]
            for c in suffix:
                assert c in allowed, f"Character {c!r} not in allowed alphabet"

    def test_secure_randomness(self) -> None:
        """Multiple generated codes should all be different."""
        codes = {generate_anonymous_code() for _ in range(100)}
        assert len(codes) == 100

    def test_validate_valid_code(self) -> None:
        assert validate_anonymous_code_format("STU-ABCD2345") is True

    def test_validate_invalid_prefix(self) -> None:
        assert validate_anonymous_code_format("XYZ-ABCD1234") is False

    def test_validate_short_code(self) -> None:
        assert validate_anonymous_code_format("STU-ABC") is False

    def test_validate_long_code(self) -> None:
        assert validate_anonymous_code_format("STU-ABCDEFGHIJ") is False

    def test_validate_disallowed_chars(self) -> None:
        assert validate_anonymous_code_format("STU-ABCDE0O1") is False  # O, 0, 1 not allowed


class TestPseudonymizationService:
    def test_get_or_create_creates_anonymous_student(self, session: Session) -> None:
        identity = StudentIdentity(encrypted_first_name="enc:Test")
        session.add(identity)
        session.flush()

        code = get_or_create_anonymous_student(session, identity.id)
        assert code.startswith("STU-")
        assert len(code) == 12

        anon = session.query(AnonymousStudent).filter_by(student_identity_id=identity.id).first()
        assert anon is not None
        assert anon.anonymous_code == code

    def test_existing_identity_reuses_code(self, session: Session) -> None:
        identity = StudentIdentity(encrypted_first_name="enc:Test")
        session.add(identity)
        session.flush()

        code1 = get_or_create_anonymous_student(session, identity.id)
        code2 = get_or_create_anonymous_student(session, identity.id)
        assert code1 == code2

    def test_different_identities_different_codes(self, session: Session) -> None:
        identity1 = StudentIdentity(encrypted_first_name="enc:Alice")
        identity2 = StudentIdentity(encrypted_first_name="enc:Bob")
        session.add_all([identity1, identity2])
        session.flush()

        code1 = get_or_create_anonymous_student(session, identity1.id)
        code2 = get_or_create_anonymous_student(session, identity2.id)
        assert code1 != code2

    def test_code_not_derived_from_identity_fields(self, session: Session) -> None:
        """Codes should not contain UUID, email, ID, name, or fingerprint."""
        import uuid
        identity_id = str(uuid.uuid4())
        identity = StudentIdentity(
            id=identity_id,
            encrypted_first_name="enc:Alice",
            encrypted_last_name="enc:Smith",
            encrypted_email="enc:alice@example.com",
            encrypted_institutional_student_id="enc:S12345",
        )
        session.add(identity)
        session.flush()

        code = get_or_create_anonymous_student(session, identity.id)

        # Code should not be derived from UUID
        assert identity_id not in code
        # Code should not contain names, emails, or IDs in any form
        assert "Alice" not in code
        assert "Smith" not in code
        assert "alice" not in code
        assert "S12345" not in code

    def test_database_uniqueness_enforced(self, session: Session) -> None:
        """Database unique constraint on anonymous_code should be enforced."""
        identity1 = StudentIdentity(encrypted_first_name="enc:Alice")
        identity2 = StudentIdentity(encrypted_first_name="enc:Bob")
        session.add_all([identity1, identity2])
        session.flush()

        anon1 = AnonymousStudent(
            student_identity_id=identity1.id,
            anonymous_code="STU-COLLISION",
        )
        anon2 = AnonymousStudent(
            student_identity_id=identity2.id,
            anonymous_code="STU-COLLISION",
        )
        session.add_all([anon1, anon2])

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            session.flush()
