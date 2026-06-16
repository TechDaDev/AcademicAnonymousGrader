# Academic Anonymous Grader — Question-Level Analytics
"""Question-level performance analysis — difficulty, discrimination,
score distribution, and flag detection.

All results are privacy-safe and never expose raw response text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analytics.filters import AnalyticsFilter, authorized_assessment_ids
from analytics.models import PrivacyState, QuestionAnalysis
from analytics.privacy import check_group_size, suppress_statistics
from analytics.statistics import (
    compute_difficulty_index,
    safe_max,
    safe_mean,
    safe_median,
    safe_min,
    safe_stdev,
)
from models.grade_record import GradeRecord
from models.question import Question
from models.submission import Submission
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Default flag thresholds
DIFFICULTY_THRESHOLD_DEFAULT = 0.4  # Below this is flagged as high difficulty
HIGH_ZERO_RATE_THRESHOLD_DEFAULT = 0.3  # Above this zero-rate is flagged
HIGH_UNANSWERED_RATE_DEFAULT = 0.3


def get_question_analysis(
    session: Session,
    ctx: AuthContext | None,
    question_id: str,
    filter_obj: AnalyticsFilter | None = None,
    difficulty_threshold: float = DIFFICULTY_THRESHOLD_DEFAULT,
    high_zero_rate_threshold: float = HIGH_ZERO_RATE_THRESHOLD_DEFAULT,
    high_unanswered_threshold: float = HIGH_UNANSWERED_RATE_DEFAULT,
) -> QuestionAnalysis:
    """Get analytics for a single question.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    question_id : str
        Question ID.
    filter_obj : AnalyticsFilter | None
        Optional filter.
    difficulty_threshold : float
        Difficulty index below this value is flagged as difficult.
    high_zero_rate_threshold : float
        Zero-score rate above this is flagged.
    high_unanswered_threshold : float
        Unanswered rate above this is flagged.

    Returns
    -------
    QuestionAnalysis
        Question analytics.
    """
    q = session.query(Question).filter(Question.id == question_id).first()
    if not q:
        return QuestionAnalysis(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    assessment_id = q.assessment_id
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id not in auth_ids:
        return QuestionAnalysis(
            privacy=PrivacyState(suppressed=True, reason="no_authorized_data")
        )

    # Get all grade records for this question
    grade_records = (
        session.query(GradeRecord)
        .filter(GradeRecord.question_id == question_id)
        .all()
    )

    graded_responses = [r for r in grade_records if r.grade is not None]
    graded_count = len(graded_responses)
    ungraded_count = len(grade_records) - graded_count

    privacy = check_group_size(graded_count, filter_obj.minimum_group_size if filter_obj else None)

    # Count submissions for this assessment to determine unanswered
    sub_count = (
        session.query(Submission)
        .filter(Submission.assessment_id == assessment_id)
        .count()
    )
    unanswered_count = max(0, sub_count - len(grade_records))

    # Grade values
    grade_values = [float(r.grade) for r in graded_responses if r.grade is not None]

    mean_val = safe_mean(grade_values)
    median_val = safe_median(grade_values)
    min_val = safe_min(grade_values)
    max_val = safe_max(grade_values)
    std_val = safe_stdev(grade_values)

    max_grade_f = float(q.maximum_grade)
    avg_pct = (
        ((mean_val / max_grade_f) * 100.0) if mean_val is not None and max_grade_f > 0 else None
    )

    # Score category counts
    full_count = sum(1 for v in grade_values if v >= max_grade_f)
    zero_count = sum(1 for v in grade_values if v <= 0)
    partial_count = sum(1 for v in grade_values if 0 < v < max_grade_f)

    # Difficulty index
    difficulty = compute_difficulty_index(mean_val, q.maximum_grade)
    difficulty_f = float(difficulty) if difficulty is not None else None

    # Correction return count
    correction_count = 0  # Would need review history; placeholder for now

    # Flags
    flags: list[str] = []
    if difficulty_f is not None and difficulty_f < difficulty_threshold:
        flags.append("high_difficulty")
    if mean_val is not None and max_grade_f > 0 and (mean_val / max_grade_f) < difficulty_threshold:
        flags.append("unusually_low_average")
    zero_rate = zero_count / graded_count if graded_count > 0 else 0
    if zero_rate > high_zero_rate_threshold:
        flags.append("high_zero_score_rate")
    unanswered_rate = unanswered_count / sub_count if sub_count > 0 else 0
    if unanswered_rate > high_unanswered_threshold:
        flags.append("high_unanswered_rate")
    if std_val is not None and mean_val is not None and mean_val > 0 and (std_val / mean_val) > 0.5:
        flags.append("high_grading_variance")
    if graded_count < (filter_obj.minimum_group_size if filter_obj else 5):
        flags.append("insufficient_data")

    return QuestionAnalysis(
        question_id=question_id,
        question_number=q.question_number,
        maximum_grade=q.maximum_grade,
        graded_response_count=graded_count,
        mean_awarded=suppress_statistics(round(mean_val, 2) if mean_val is not None else None, privacy),
        median_awarded=suppress_statistics(round(median_val, 2) if median_val is not None else None, privacy),
        minimum_awarded=suppress_statistics(round(min_val, 2) if min_val is not None else None, privacy),
        maximum_awarded=suppress_statistics(round(max_val, 2) if max_val is not None else None, privacy),
        standard_deviation=suppress_statistics(round(std_val, 2) if std_val is not None else None, privacy),
        average_percentage=suppress_statistics(round(avg_pct, 1) if avg_pct is not None else None, privacy),
        full_score_count=full_count,
        zero_score_count=zero_count,
        partial_credit_count=partial_count,
        unanswered_count=unanswered_count,
        ungraded_count=ungraded_count,
        difficulty_index=suppress_statistics(round(difficulty_f, 3) if difficulty_f is not None else None, privacy),
        correction_return_count=correction_count,
        flags=flags,
        privacy=privacy,
    )


def list_question_analyses(
    session: Session,
    ctx: AuthContext | None,
    assessment_id: str,
    filter_obj: AnalyticsFilter | None = None,
) -> list[QuestionAnalysis]:
    """Get question-level analytics for all questions in an assessment.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    assessment_id : str
        Assessment ID.
    filter_obj : AnalyticsFilter | None
        Optional filter.

    Returns
    -------
    list[QuestionAnalysis]
        List of question analyses.
    """
    auth_ids = authorized_assessment_ids(session, ctx, filter_obj)
    if assessment_id not in auth_ids:
        return []

    questions = (
        session.query(Question)
        .filter(Question.assessment_id == assessment_id)
        .order_by(Question.question_number)
        .all()
    )

    return [
        get_question_analysis(session, ctx, q.id, filter_obj)
        for q in questions
    ]
