# Academic Anonymous Grader — Logging Privacy Tests
"""Tests for services/logging_service.py privacy protections."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

from models.response import Response
from models.student_identity import StudentIdentity
from services.logging_service import PrivacyRedactionFilter, configure_logging


class TestPrivacyRedaction:
    """Verify that sensitive patterns are redacted from logs."""

    @staticmethod
    def _capture_log(message: str, logger_name: str = "test_privacy") -> str:
        """Send a log message and capture the output."""
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.addFilter(PrivacyRedactionFilter())
        logger.addHandler(handler)

        logger.info(message)
        return stream.getvalue()

    def test_email_content_is_redacted(self) -> None:
        """Email addresses in log messages should be redacted."""
        output = self._capture_log("User email is student@example.com")
        assert "[EMAIL_REDACTED]" in output
        assert "student@example.com" not in output

    def test_secret_key_content_is_redacted(self) -> None:
        """Secret key assignments should be redacted."""
        output = self._capture_log("ENCRYPTION_KEY=my-super-secret-key-value")
        assert "[REDACTED]" in output
        assert "my-super-secret-key-value" not in output

    def test_api_key_content_is_redacted(self) -> None:
        """API key assignments should be redacted."""
        output = self._capture_log("API_KEY=sk-1234567890abcdef1234567890abcdef")
        assert "[REDACTED]" in output
        assert "sk-1234567890abcdef1234567890abcdef" not in output

    def test_long_alphanumeric_token_is_redacted(self) -> None:
        """32+ character alphanumeric strings that look like keys should be redacted."""
        output = self._capture_log("token=abcdefghijklmnopqrstuvwxyz123456")
        assert "abcdefghijklmnopqrstuvwxyz123456" not in output

    def test_bearer_token_is_redacted(self) -> None:
        """Bearer tokens should be redacted."""
        output = self._capture_log("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.token")
        assert "[REDACTED]" in output
        assert "eyJhbGciOiJIUzI1NiJ9.token" not in output


class TestModelReprPrivacy:
    """Verify that model __repr__ methods do not expose sensitive data."""

    def test_student_identity_repr_no_pii(self) -> None:
        """StudentIdentity.__repr__ must not contain PII."""
        identity = StudentIdentity(
            first_name="Confidential",
            last_name="User",
            email="secret@example.com",
            institutional_student_id="S12345",
        )
        representation = repr(identity)
        assert "Confidential" not in representation
        assert "secret@example.com" not in representation
        assert "S12345" not in representation

    def test_response_repr_no_text(self) -> None:
        """Response.__repr__ must not contain response text."""
        response = Response(response_text="This is a secret answer")
        representation = repr(response)
        assert "secret answer" not in representation


class TestLoggerConfiguration:
    """Verify logger initialization does not duplicate handlers."""

    def test_configure_logging_does_not_duplicate_handlers(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = configure_logging(log_file=log_file, log_level="DEBUG")
        initial_count = len(logger.handlers)

        # Second call should not add handlers
        logger2 = configure_logging(log_file=log_file, log_level="DEBUG")
        assert len(logger2.handlers) == initial_count
