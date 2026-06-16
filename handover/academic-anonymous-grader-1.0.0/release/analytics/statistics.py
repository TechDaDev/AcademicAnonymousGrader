# Academic Anonymous Grader — Analytics Statistics
"""Statistical calculation helpers for analytics.

All functions operate on lists of numeric values and return safe,
typed results. Handles empty lists, None values, and edge cases
without raising exceptions.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal


def safe_mean(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the mean of a sequence, ignoring None values.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Sequence of numeric values.

    Returns
    -------
    float | None
        Mean value, or None if the sequence is empty.
    """
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def safe_median(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the median of a sequence, ignoring None values.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Sequence of numeric values.

    Returns
    -------
    float | None
        Median value, or None if the sequence is empty.
    """
    cleaned = sorted([float(v) for v in values if v is not None])
    if not cleaned:
        return None
    n = len(cleaned)
    if n % 2 == 1:
        return cleaned[n // 2]
    return (cleaned[n // 2 - 1] + cleaned[n // 2]) / 2.0


def safe_min(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the minimum of a sequence, ignoring None values."""
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return min(cleaned)


def safe_max(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the maximum of a sequence, ignoring None values."""
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return max(cleaned)


def safe_stdev(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the sample standard deviation, ignoring None values.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Sequence of numeric values.

    Returns
    -------
    float | None
        Standard deviation, or None if fewer than 2 values.
    """
    cleaned = [float(v) for v in values if v is not None]
    if len(cleaned) < 2:
        return None
    mean_val = sum(cleaned) / len(cleaned)
    variance = sum((x - mean_val) ** 2 for x in cleaned) / (len(cleaned) - 1)
    return math.sqrt(variance)


def safe_quartiles(values: Sequence[float | Decimal | None]) -> tuple[float | None, float | None, float | None]:
    """Calculate Q1, Q2 (median), Q3 quartiles.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Sequence of numeric values.

    Returns
    -------
    tuple[float | None, float | None, float | None]
        (Q1, Q2, Q3) or (None, None, None) if empty.
    """
    cleaned = sorted([float(v) for v in values if v is not None])
    if not cleaned:
        return None, None, None
    n = len(cleaned)
    q2 = safe_median(cleaned)
    lower_half = cleaned[: n // 2]
    upper_half = cleaned[(n + 1) // 2 :]
    q1 = safe_median(lower_half) if lower_half else None
    q3 = safe_median(upper_half) if upper_half else None
    return q1, q2, q3


def safe_variance(values: Sequence[float | Decimal | None]) -> float | None:
    """Calculate the sample variance, ignoring None values."""
    cleaned = [float(v) for v in values if v is not None]
    if len(cleaned) < 2:
        return None
    mean_val = sum(cleaned) / len(cleaned)
    return sum((x - mean_val) ** 2 for x in cleaned) / (len(cleaned) - 1)


def normalize_percentage(
    value: float | Decimal,
    maximum: float | Decimal,
) -> float:
    """Safely normalize a value to a percentage.

    Parameters
    ----------
    value : float | Decimal
        The raw value.
    maximum : float | Decimal
        The maximum possible value.

    Returns
    -------
    float
        Percentage (0.0 to 100.0), or 0.0 if maximum is zero.
    """
    max_f = float(maximum)
    if max_f <= 0:
        return 0.0
    return (float(value) / max_f) * 100.0


def compute_pass_fail(
    values: Sequence[float | Decimal | None],
    pass_threshold_pct: float = 50.0,
    maximum: float | Decimal = 100.0,
) -> tuple[int, int, float]:
    """Compute pass/fail counts and pass percentage.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Grade values.
    pass_threshold_pct : float
        Minimum percentage to pass (default 50.0).
    maximum : float | Decimal
        Maximum possible grade.

    Returns
    -------
    tuple[int, int, float]
        (pass_count, fail_count, pass_percentage).
    """
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return 0, 0, 0.0
    max_f = float(maximum)
    if max_f <= 0:
        return 0, 0, 0.0
    pass_count = 0
    fail_count = 0
    for v in cleaned:
        pct = (v / max_f) * 100.0
        if pct >= pass_threshold_pct:
            pass_count += 1
        else:
            fail_count += 1
    pass_pct = (pass_count / len(cleaned)) * 100.0 if cleaned else 0.0
    return pass_count, fail_count, pass_pct


def compute_difficulty_index(
    mean_grade: float | None,
    maximum_grade: float | Decimal,
) -> float | None:
    """Calculate the difficulty index for a question.

    Difficulty index = mean awarded grade / maximum grade.

    Interpretation:
        - 0.0–0.3: Difficult
        - 0.3–0.7: Moderate
        - 0.7–1.0: Easy

    Parameters
    ----------
    mean_grade : float | None
        Mean awarded grade.
    maximum_grade : float | Decimal
        Maximum possible grade.

    Returns
    -------
    float | None
        Difficulty index (0.0 to 1.0), or None if unavailable.
    """
    if mean_grade is None:
        return None
    max_f = float(maximum_grade)
    if max_f <= 0:
        return None
    return mean_grade / max_f


def compute_grade_bands(
    values: Sequence[float | Decimal | None],
    maximum: float | Decimal,
    bands: list[tuple[float, float, str]] | None = None,
) -> list[dict[str, object]]:
    """Compute grade band distribution.

    Parameters
    ----------
    values : Sequence[float | Decimal | None]
        Grade values.
    maximum : float | Decimal
        Maximum possible grade.
    bands : list[tuple[float, float, str]] | None
        List of (min_pct, max_pct, label) tuples.

    Returns
    -------
    list[dict]
        List of band dicts with label, count, percentage.
    """
    if bands is None:
        bands = [
            (90.0, 100.0, "90–100%"),
            (80.0, 89.99, "80–89.99%"),
            (70.0, 79.99, "70–79.99%"),
            (60.0, 69.99, "60–69.99%"),
            (50.0, 59.99, "50–59.99%"),
            (0.0, 49.99, "Below 50%"),
        ]

    cleaned = [float(v) for v in values if v is not None]
    max_f = float(maximum)
    if max_f <= 0 or not cleaned:
        return [
            {"label": label, "min_pct": min_p, "max_pct": max_p, "count": 0, "percentage": 0.0}
            for min_p, max_p, label in bands
        ]

    total = len(cleaned)
    result = []
    for min_pct, max_pct, label in bands:
        count = 0
        for v in cleaned:
            pct = (v / max_f) * 100.0
            if min_pct <= pct <= max_pct:
                count += 1
        result.append({
            "label": label,
            "min_pct": min_pct,
            "max_pct": max_pct,
            "count": count,
            "percentage": (count / total) * 100.0,
        })
    return result
