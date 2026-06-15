"""Export identity service tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.import_batch import ImportBatch
from models.material import Material
from models.student_identity import StudentIdentity
from security.encryption import encrypt_text
from security.key_validation import _decode_key
from security.models import EncryptionKey
from services.exceptions import ExportIdentityDecryptionError
from services.export_identity_service import get_export_identity


def _setup(session: Session, settings) -> dict:  # type: ignore[type-arg]
    key = EncryptionKey(_decode_key(settings.identity_encryption_key, "IDENTITY_ENCRYPTION_KEY", 32))
    material = Material(name="EI Test"); session.add(material); session.flush()
    assessment = Assessment(material_id=material.id, title="EI", maximum_grade=Decimal("100"))
    session.add(assessment); session.flush()
    batch = ImportBatch(assessment_id=assessment.id, source_filename="t.html"); session.add(batch); session.flush()
    identity = StudentIdentity(
        encrypted_first_name=encrypt_text(key, "Ahmed"),
        encrypted_last_name=encrypt_text(key, "Hassan"),
        encrypted_email=encrypt_text(key, "ahmed@example.com"),
    )
    session.add(identity); session.flush()
    anon = AnonymousStudent(student_identity_id=identity.id, anonymous_code="STU-EI001")
    session.add(anon); session.flush()
    return {"anon": anon, "settings": settings}


class TestExportIdentity:
    def test_decrypts_correctly(self, session: Session, monkeypatch) -> None:
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", "8k7lYYckaMaqKDy31LgQhPCTvSup2elJtoEm0TEztXY=")
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", "yQH1YtA5kQtrilNmVo_qxLT0Yty4sl4k5vZMDnxgp-c=")
        from config import get_settings
        settings = get_settings()
        data = _setup(session, settings)
        ei = get_export_identity(session, data["anon"].id, settings)
        assert ei.first_name == "Ahmed"
        assert ei.last_name == "Hassan"
        assert ei.full_name == "Ahmed Hassan"
        assert ei.email == "ahmed@example.com"

    def test_nonexistent_raises(self, session: Session, monkeypatch) -> None:
        monkeypatch.setenv("IDENTITY_ENCRYPTION_KEY", "8k7lYYckaMaqKDy31LgQhPCTvSup2elJtoEm0TEztXY=")
        monkeypatch.setenv("IDENTITY_FINGERPRINT_KEY", "yQH1YtA5kQtrilNmVo_qxLT0Yty4sl4k5vZMDnxgp-c=")
        from config import get_settings
        settings = get_settings()
        with pytest.raises(ExportIdentityDecryptionError):
            get_export_identity(session, "nonexistent", settings)
