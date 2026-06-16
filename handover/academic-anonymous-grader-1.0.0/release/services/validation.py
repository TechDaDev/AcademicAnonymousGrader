# Academic Anonymous Grader — Validation Utilities
"""Reusable validation helpers for materials, assessments, and questions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def normalize_optional_text(value: str | None, max_length: int | None = None) -> str | None:
    """Trim whitespace; return None for blank or whitespace-only strings.

    Parameters
    ----------
    value : str | None
        Raw input value.
    max_length : int | None
        If set, raise ValueError when the trimmed value exceeds this length.

    Returns
    -------
    str | None
        Trimmed string or None.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if max_length is not None and len(stripped) > max_length:
        msg = f"Value must not exceed {max_length} characters, got {len(stripped)}"
        raise ValueError(msg)
    return stripped


def normalize_required_text(value: str | None, max_length: int | None = None) -> str:
    """Trim whitespace; raise ValueError for blank or missing strings.

    Parameters
    ----------
    value : str | None
        Raw input value.
    max_length : int | None
        If set, raise when trimmed value exceeds this length.

    Returns
    -------
    str
        Trimmed non-empty string.
    """
    if value is None:
        msg = "Value is required and must not be blank"
        raise ValueError(msg)
    stripped = value.strip()
    if not stripped:
        msg = "Value is required and must not be blank"
        raise ValueError(msg)
    if max_length is not None and len(stripped) > max_length:
        msg = f"Value must not exceed {max_length} characters, got {len(stripped)}"
        raise ValueError(msg)
    return stripped


def validate_positive_decimal(value: object, field_name: str = "value") -> Decimal:
    """Validate and return a positive Decimal with at most 2 decimal places.

    Parameters
    ----------
    value : object
        Input to validate.
    field_name : str
        Name for error messages.

    Returns
    -------
    Decimal
        Positive Decimal value.

    Raises
    ------
    ValueError
        If value is not a valid positive Decimal or has > 2 decimal places.
    """
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        msg = f"{field_name} must be a valid number"
        raise ValueError(msg) from exc

    if d <= Decimal("0"):
        msg = f"{field_name} must be greater than zero"
        raise ValueError(msg)

    if d.as_tuple().exponent < -2:  # type: ignore[operator]  # exponent is negative int or 0
        msg = f"{field_name} must have at most 2 decimal places"
        raise ValueError(msg)

    return d


def validate_positive_int(value: object, field_name: str = "value") -> int:
    """Validate that value is a positive integer.

    Parameters
    ----------
    value : object
        Input to validate.
    field_name : str
        Name for error messages.

    Returns
    -------
    int
        Positive integer.
    """
    try:
        n = int(str(value))
    except (ValueError, TypeError) as exc:
        msg = f"{field_name} must be a valid integer"
        raise ValueError(msg) from exc
    if n <= 0:
        msg = f"{field_name} must be greater than zero"
        raise ValueError(msg)
    return n


def validate_question_total(
    question_total: Decimal, assessment_maximum: Decimal
) -> tuple[bool, Decimal, str]:
    """Validate that question total equals assessment maximum.

    Parameters
    ----------
    question_total : Decimal
        Sum of all question maximum grades.
    assessment_maximum : Decimal
        Assessment maximum grade.

    Returns
    -------
    tuple[bool, Decimal, str]
        (is_valid, difference, message)
    """
    diff = assessment_maximum - question_total
    if diff == Decimal("0"):
        return True, diff, "Configuration valid — question total matches assessment maximum"
    if diff > Decimal("0"):
        return False, diff, f"Question total is {diff} below assessment maximum"
    return False, diff, f"Question total exceeds assessment maximum by {abs(diff)}"


ALLOWED_ASSESSMENT_STATUSES = {"draft", "ready", "archived"}

PROTECTED_ASSESSMENT_STATUSES = {"grading", "finalized", "reopened"}

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "archived"},
    "ready": {"draft", "archived"},
    "archived": {"draft", "ready"},
    "grading": set(),
    "finalized": {"reopened"},
    "reopened": {"finalized"},
}


def validate_status_transition(
    current_status: str, new_status: str
) -> None:
    """Validate an assessment status transition.

    Raises
    ------
    ValueError
        If the transition is not allowed.
    """
    if current_status == new_status:
        return
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        msg = f"Cannot transition from '{current_status}' to '{new_status}'"
        raise ValueError(msg)
