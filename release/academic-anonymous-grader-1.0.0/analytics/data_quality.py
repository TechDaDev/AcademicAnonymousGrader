# Academic Anonymous Grader — Data Quality Report
"""Administrator-only data quality report for detecting inconsistent,
orphaned, or unexpected records.

Never exposes student identity, responses, feedback, or individual grades.
Uses safe counts and record references only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func

from analytics.models import DataQualityIssue, DataQualityReport
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.instructor_assignment import InstructorAssignment
from models.question import Question
from models.submission import Submission
from models.user import User
from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_data_quality_report(
    session: Session,
    ctx: AuthContext | None,
) -> DataQualityReport:
    """Generate a data quality report.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context. Must be administrator.

    Returns
    -------
    DataQualityReport
        Data quality issues.
    """
    if ctx is None or ctx.role != "administrator":
        return DataQualityReport()

    issues: list[DataQualityIssue] = []

    # Submissions with missing responses
    missing_resp = (
        session.query(Submission)
        .outerjoin(Submission.responses)
        .filter(Submission.responses == None)  # noqa: E711
        .count()
    )
    if missing_resp > 0:
        issues.append(
            DataQualityIssue(
                issue_type="missing_responses",
                severity="warning",
                count=missing_resp,
                description=f"{missing_resp} submission(s) have no responses.",
            )
        )

    # Ungraded questions
    ungraded = (
        session.query(GradeRecord)
        .filter(GradeRecord.grading_status == "ungraded")
        .count()
    )
    if ungraded > 0:
        issues.append(
            DataQualityIssue(
                issue_type="ungraded_questions",
                severity="warning",
                count=ungraded,
                description=f"{ungraded} question grade(s) are still ungraded.",
            )
        )

    # Grades outside valid range
    invalid_grades = (
        session.query(GradeRecord)
        .join(GradeRecord.question)
        .filter(
            GradeRecord.grade.isnot(None),
            GradeRecord.grade > Question.maximum_grade,
        )
        .count()
    )
    if invalid_grades > 0:
        issues.append(
            DataQualityIssue(
                issue_type="grades_above_maximum",
                severity="critical",
                count=invalid_grades,
                description=f"{invalid_grades} grade(s) exceed the question maximum.",
            )
        )

    # Assessment total mismatch
    mismatched = (
        session.query(Assessment)
        .outerjoin(Assessment.questions)
        .group_by(Assessment.id)
        .having(
            func.coalesce(func.sum(Question.maximum_grade), 0) != Assessment.maximum_grade
        )
        .count()
    )
    if mismatched > 0:
        issues.append(
            DataQualityIssue(
                issue_type="assessment_total_mismatch",
                severity="warning",
                count=mismatched,
                description=f"{mismatched} assessment(s) have question totals that don't match the maximum grade.",
            )
        )

    # Stale grading claims
    now = datetime.now(UTC)
    now - timedelta(hours=4)
    stale_claims = (
        session.query(Submission)
        .filter(
            Submission.grading_status == "pending",
            Submission.assigned_grader_user_id.isnot(None),
            Submission.grading_lock_expires_at <= now,
        )
        .count()
    )
    if stale_claims > 0:
        issues.append(
            DataQualityIssue(
                issue_type="stale_grading_claims",
                severity="information",
                count=stale_claims,
                description=f"{stale_claims} stale grading claim(s) exist.",
            )
        )

    # Assessments without questions
    no_questions = (
        session.query(Assessment)
        .outerjoin(Assessment.questions)
        .group_by(Assessment.id)
        .having(func.count(Question.id) == 0)
        .count()
    )
    if no_questions > 0:
        issues.append(
            DataQualityIssue(
                issue_type="assessments_without_questions",
                severity="warning",
                count=no_questions,
                description=f"{no_questions} assessment(s) have no questions configured.",
            )
        )

    # Questions with invalid maximum grade
    invalid_question_max = (
        session.query(Question)
        .filter(Question.maximum_grade <= 0)
        .count()
    )
    if invalid_question_max > 0:
        issues.append(
            DataQualityIssue(
                issue_type="invalid_question_maximum",
                severity="critical",
                count=invalid_question_max,
                description=f"{invalid_question_max} question(s) have invalid maximum grades (<= 0).",
            )
        )

    # Archived users with active assignments
    archived_active = (
        session.query(InstructorAssignment)
        .join(User, InstructorAssignment.instructor_user_id == User.id)
        .filter(
            InstructorAssignment.is_active == True,  # noqa: E712
            User.is_active == False,  # noqa: E712
        )
        .count()
    )
    if archived_active > 0:
        issues.append(
            DataQualityIssue(
                issue_type="archived_users_active_assignments",
                severity="warning",
                count=archived_active,
                description=f"{archived_active} archived user(s) have active instructor assignments.",
            )
        )

    # ── Phase 12.1 — Academic structure checks ─────────────────────
    from models.academic_year import AcademicYear
    from models.department import Department
    from models.material import Material as MaterialModel

    # Critical: broken classification foreign keys
    broken_dept_fk = (
        session.query(MaterialModel)
        .filter(
            MaterialModel.department_id.isnot(None),
            ~MaterialModel.department_id.in_(
                session.query(Department.id).filter(Department.id.isnot(None))
            ),
        )
        .count()
    )
    if broken_dept_fk > 0:
        issues.append(
            DataQualityIssue(
                issue_type="broken_department_fk",
                severity="critical",
                count=broken_dept_fk,
                description=f"{broken_dept_fk} material(s) reference non-existent departments.",
            )
        )

    # Critical: multiple current academic years
    current_years = (
        session.query(AcademicYear)
        .filter(AcademicYear.is_current == True)  # noqa: E712
        .count()
    )
    if current_years > 1:
        issues.append(
            DataQualityIssue(
                issue_type="multiple_current_academic_years",
                severity="critical",
                count=current_years,
                description=f"{current_years} academic years are marked as current (expected at most 1).",
            )
        )

    # Critical: material missing required classification after review completed
    incomplete_after_review = (
        session.query(MaterialModel)
        .filter(
            MaterialModel.classification_needs_review == False,  # noqa: E712
            MaterialModel.is_archived == False,  # noqa: E712
        )
        .filter(
            (MaterialModel.department_id.is_(None))
            | (MaterialModel.academic_stage_id.is_(None))
            | (MaterialModel.academic_term_id.is_(None))
            | (MaterialModel.academic_year_id.is_(None))
        )
        .count()
    )
    if incomplete_after_review > 0:
        issues.append(
            DataQualityIssue(
                issue_type="incomplete_classification_after_review",
                severity="critical",
                count=incomplete_after_review,
                description=(
                    f"{incomplete_after_review} active material(s) "
                    "marked complete but missing classification refs."
                ),
            )
        )

    # Warning: classification_needs_review
    needs_review_count = (
        session.query(MaterialModel)
        .filter(MaterialModel.classification_needs_review == True)  # noqa: E712
        .count()
    )
    if needs_review_count > 0:
        issues.append(
            DataQualityIssue(
                issue_type="classification_needs_review",
                severity="warning",
                count=needs_review_count,
                description=f"{needs_review_count} material(s) need classification review.",
            )
        )

    # Warning: no current academic year
    if current_years == 0:
        issues.append(
            DataQualityIssue(
                issue_type="no_current_academic_year",
                severity="warning",
                count=1,
                description="No academic year is marked as current.",
            )
        )

    # Warning: invalid academic year range
    invalid_year_range = (
        session.query(AcademicYear)
        .filter(AcademicYear.end_year != AcademicYear.start_year + 1)
        .count()
    )
    if invalid_year_range > 0:
        issues.append(
            DataQualityIssue(
                issue_type="invalid_academic_year_range",
                severity="warning",
                count=invalid_year_range,
                description=f"{invalid_year_range} academic year(s) have invalid start/end year range.",
            )
        )

    # Warning: active material using archived reference
    active_archived_dept = (
        session.query(MaterialModel)
        .join(Department, MaterialModel.department_id == Department.id)
        .filter(
            MaterialModel.is_archived == False,  # noqa: E712
            Department.is_active == False,  # noqa: E712
            MaterialModel.department_id.isnot(None),
        )
        .count()
    )
    if active_archived_dept > 0:
        desc = f"{active_archived_dept} active material(s) use an archived department."
        issues.append(
            DataQualityIssue(
                issue_type="active_material_archived_department",
                severity="information",
                count=active_archived_dept,
                description=desc,
            )
        )

    # Check for duplicate active assignments (should be blocked by index, but check anyway)
    dup_assignments = (
        session.query(
            InstructorAssignment.instructor_user_id,
            InstructorAssignment.assessment_id,
            func.count().label("cnt"),
        )
        .filter(InstructorAssignment.is_active == True)  # noqa: E712
        .group_by(
            InstructorAssignment.instructor_user_id,
            InstructorAssignment.assessment_id,
        )
        .having(func.count() > 1)
        .count()
    )
    if dup_assignments > 0:
        issues.append(
            DataQualityIssue(
                issue_type="duplicate_active_assignments",
                severity="critical",
                count=dup_assignments,
                description=f"{dup_assignments} duplicate active assignment(s) detected.",
            )
        )

    return DataQualityReport(
        issues=issues,
        total_issues=len(issues),
        critical_count=sum(1 for i in issues if i.severity == "critical"),
        warning_count=sum(1 for i in issues if i.severity == "warning"),
        info_count=sum(1 for i in issues if i.severity == "information"),
    )
