# Academic Anonymous Grader — Export Identity Service
"""Safe identity restoration for export only.

SAFETY:
- Identities may be decrypted ONLY inside the export workflow.
- Decrypted values are returned as a short-lived typed object.
- Never write decrypted values back to the database.
- Never store decrypted values in long-lived Streamlit session state.
- Never log decrypted values.
- Clear references after workbook generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from models.student_identity import StudentIdentity
from security.encryption import decrypt_text
from security.key_validation import _decode_key
from security.models import EncryptionKey
from services.exceptions import ExportIdentityDecryptionError
from services.logging_service import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from config import Settings

logger = get_logger("export_identity")


@dataclass(frozen=True, slots=True)
class ExportIdentity:
    """Short-lived typed identity for workbook rows.

    Never persist this object beyond workbook generation.
    """

    first_name: str
    last_name: str
    full_name: str
    email: str
    institutional_student_id: str | None


def _load_encryption_key(settings: Settings) -> EncryptionKey:
    """Load and validate the encryption key for export decryption."""
    raw = settings.identity_encryption_key
    if not raw:
        raise ExportIdentityDecryptionError("IDENTITY_ENCRYPTION_KEY is not set")
    key_bytes = _decode_key(raw, "IDENTITY_ENCRYPTION_KEY", 32)
    return EncryptionKey(key_bytes)


def get_export_identity(
    session: Session,
    anonymous_student_id: str,
    settings: Settings,
) -> ExportIdentity:
    """Decrypt and return identity for an anonymous student.

    Parameters
    ----------
    session : Session
        Database session.
    anonymous_student_id : str
        The AnonymousStudent.id to look up.
    settings : Settings
        Application settings (provides the encryption key).

    Returns
    -------
    ExportIdentity
        Decrypted identity fields.

    Raises
    ------
    ExportIdentityDecryptionError
        If decryption fails or the identity cannot be found.
    """
    from models.anonymous_student import AnonymousStudent

    anon = (
        session.query(AnonymousStudent)
        .filter(AnonymousStudent.id == anonymous_student_id)
        .first()
    )
    if anon is None or anon.student_identity is None:
        raise ExportIdentityDecryptionError(
            f"No identity found for anonymous student {anonymous_student_id[:8]}"
        )

    identity: StudentIdentity = anon.student_identity

    try:
        ekey = _load_encryption_key(settings)
        first_name = decrypt_text(ekey, identity.encrypted_first_name) or ""
        last_name = decrypt_text(ekey, identity.encrypted_last_name) or ""
        email = decrypt_text(ekey, identity.encrypted_email) or ""

        inst_id = None
        if identity.encrypted_institutional_student_id:
            inst_id = decrypt_text(ekey, identity.encrypted_institutional_student_id)

        full_name = f"{first_name} {last_name}".strip()

        return ExportIdentity(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name or email.split("@")[0] if email else "Unknown",
            email=email,
            institutional_student_id=inst_id,
        )
    except ExportIdentityDecryptionError:
        raise
    except Exception as exc:
        raise ExportIdentityDecryptionError(
            f"Failed to decrypt identity for {anonymous_student_id[:8]}: {exc}"
        ) from exc
