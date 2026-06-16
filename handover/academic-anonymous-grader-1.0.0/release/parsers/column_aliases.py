"""Canonical column names and alias helpers."""

from __future__ import annotations

from parsers.normalization import extract_response_number, normalize_lookup_key

COLUMN_ALIASES: dict[str, str] = {
    "first name": "first_name",
    "given name": "first_name",
    "student first name": "first_name",
    "last name": "last_name",
    "surname": "last_name",
    "family name": "last_name",
    "email": "email",
    "e mail": "email",
    "email address": "email",
    "student email": "email",
    "student id": "institutional_student_id",
    "student number": "institutional_student_id",
    "registration number": "institutional_student_id",
    "university id": "institutional_student_id",
    "institutional id": "institutional_student_id",
    "institutional i d": "institutional_student_id",
    "institutional student id": "institutional_student_id",
    "status": "status",
    "submission status": "status",
    "started": "started",
    "start time": "started",
    "started at": "started",
    "completed": "completed",
    "completion time": "completed",
    "submitted at": "completed",
    "duration": "duration",
    "time taken": "duration",
    "grade": "source_grade",
    "score": "source_grade",
    "existing grade": "source_grade",
    "grade 10": "source_grade",
    "grade 10 00": "source_grade",
}


def get_mapped_field(normalized_header: str) -> str | None:
    return COLUMN_ALIASES.get(normalize_lookup_key(normalized_header))


def mapped_response_number(header: str | None) -> int | None:
    return extract_response_number(header)
