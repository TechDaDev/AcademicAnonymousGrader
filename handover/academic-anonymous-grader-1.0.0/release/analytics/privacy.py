# Academic Anonymous Grader — Analytics Privacy Thresholds
"""Privacy-safe suppression for small groups in analytics reports.

The configured minimum group size controls when detailed statistics are
suppressed to prevent re-identification of individual students.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from analytics.models import PrivacyState

# Absolute minimum group size allowed in production
ABSOLUTE_MINIMUM_GROUP_SIZE: int = 3
# Default minimum group size
DEFAULT_MINIMUM_GROUP_SIZE: int = 5


def check_group_size(
    actual_size: int,
    minimum_size: int | None = None,
) -> PrivacyState:
    """Check whether a group meets the minimum size threshold.

    Parameters
    ----------
    actual_size : int
        The actual number of items in the group.
    minimum_size : int | None
        The minimum allowed group size. Uses default if None.

    Returns
    -------
    PrivacyState
        Suppressed state if the group is too small.
    """
    if minimum_size is None:
        minimum_size = DEFAULT_MINIMUM_GROUP_SIZE

    if actual_size < minimum_size:
        return PrivacyState(
            suppressed=True,
            reason="insufficient_group_size",
            minimum_group_size=minimum_size,
            actual_group_size=actual_size,
        )
    return PrivacyState(
        suppressed=False,
        minimum_group_size=minimum_size,
        actual_group_size=actual_size,
    )


def suppress_statistics(
    value: float | None,
    privacy: PrivacyState,
) -> float | None:
    """Return None if suppressed, otherwise the value.

    Parameters
    ----------
    value : float | None
        The value to potentially suppress.
    privacy : PrivacyState
        The privacy state.

    Returns
    -------
    float | None
        None if suppressed, otherwise the original value.
    """
    if privacy.suppressed:
        return None
    return value


def suppress_decimal(
    value: Decimal | None,
    privacy: PrivacyState,
) -> Decimal | None:
    """Return None if suppressed, otherwise the value."""
    if privacy.suppressed:
        return None
    return value


def suppress_int(
    value: int,
    privacy: PrivacyState,
) -> int:
    """Return 0 if suppressed, otherwise the value.

    For counts, suppression means returning 0 to avoid revealing
    that a small group exists.
    """
    if privacy.suppressed:
        return 0
    return value


def suppress_all_distribution(
    bands: list[Any],
    privacy: PrivacyState,
) -> list[Any]:
    """Suppress all distribution data when the group is too small."""
    if privacy.suppressed:
        return []
    return bands
