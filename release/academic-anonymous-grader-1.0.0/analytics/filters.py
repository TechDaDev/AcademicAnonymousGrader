# Academic Anonymous Grader — Analytics Filter Model
"""Reusable AnalyticsFilter for scoping analytics queries.

Every public analytics function accepts an AnalyticsFilter to control
which data is included. The filter is validated against the caller's
authorization context before execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from services.authorization_service import AuthContext

if TYPE_CHECKING:
    from sqlalchemy.orm import Session



# Default minimum group size for privacy threshold
ANALYTICS_MINIMUM_GROUP_SIZE_DEFAULT: int = 5

# Allowed sort directions
SORT_ASC = "asc"
SORT_DESC = "desc"
_VALID_SORT_DIRECTIONS = {SORT_ASC, SORT_DESC}


@dataclass
class AnalyticsFilter:
    """Filter parameters for analytics queries.

    All fields are optional. Validation ensures consistency and
    authorization safety.
    """

    material_id: str | None = None
    assessment_id: str | None = None
    instructor_user_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    submission_statuses: list[str] | None = None
    grading_statuses: list[str] | None = None
    include_archived: bool = False
    include_finalized: bool = True
    question_id: str | None = None
    minimum_group_size: int = ANALYTICS_MINIMUM_GROUP_SIZE_DEFAULT
    sort_by: str = "title"
    sort_direction: str = SORT_ASC
    # Phase 12.1 — Classification filters
    department_id: str | None = None
    academic_stage_id: str | None = None
    academic_term_id: str | None = None
    academic_year_id: str | None = None

    def validate(
        self,
        session: Session,
        ctx: AuthContext | None,
    ) -> list[str]:
        """Validate the filter against the database and auth context.

        Returns a list of error messages. Empty list means valid.

        Parameters
        ----------
        session : Session
            Database session.
        ctx : AuthContext | None
            Authorization context.

        Returns
        -------
        list[str]
            Validation error messages.
        """
        errors: list[str] = []

        # Validate sort direction
        if self.sort_direction not in _VALID_SORT_DIRECTIONS:
            errors.append(f"Invalid sort direction: '{self.sort_direction}'.")

        # Validate date range
        if self.date_from and self.date_to and self.date_from > self.date_to:
            errors.append("date_from must be before date_to.")

        # Validate minimum group size
        if self.minimum_group_size < 1:
            errors.append("minimum_group_size must be at least 1.")

        # Validate material_id if assessment_id is set
        if self.material_id and self.assessment_id:
            from models.assessment import Assessment

            asmt = (
                session.query(Assessment)
                .filter(Assessment.id == self.assessment_id)
                .first()
            )
            if asmt and asmt.material_id != self.material_id:
                errors.append("Assessment does not belong to the selected material.")

        # Validate question_id belongs to assessment
        if self.question_id and self.assessment_id:
            from models.question import Question

            q = (
                session.query(Question)
                .filter(Question.id == self.question_id)
                .first()
            )
            if q and q.assessment_id != self.assessment_id:
                errors.append("Question does not belong to the selected assessment.")

        # Validate classification references exist
        if self.department_id:
            from models.department import Department
            dept = session.query(Department).filter(Department.id == self.department_id).first()
            if not dept:
                errors.append("Selected department not found.")
            elif ctx and ctx.role != "administrator":
                # Check department is accessible via assigned materials
                from models.assessment import Assessment
                from models.instructor_assignment import InstructorAssignment
                from models.material import Material
                accessible = (
                    session.query(Material.id)
                    .filter(Material.department_id == self.department_id)
                    .join(Assessment, Assessment.material_id == Material.id)
                    .join(InstructorAssignment, InstructorAssignment.assessment_id == Assessment.id)
                    .filter(
                        InstructorAssignment.instructor_user_id == ctx.user_id,
                        InstructorAssignment.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if not accessible:
                    errors.append("Department not available for analytics.")

        if self.academic_stage_id:
            from models.academic_stage import AcademicStage
            stage = session.query(AcademicStage).filter(AcademicStage.id == self.academic_stage_id).first()
            if not stage:
                errors.append("Selected stage not found.")
            elif ctx and ctx.role != "administrator":
                from models.assessment import Assessment
                from models.instructor_assignment import InstructorAssignment
                from models.material import Material
                accessible = (
                    session.query(Material.id)
                    .filter(Material.academic_stage_id == self.academic_stage_id)
                    .join(Assessment, Assessment.material_id == Material.id)
                    .join(InstructorAssignment, InstructorAssignment.assessment_id == Assessment.id)
                    .filter(
                        InstructorAssignment.instructor_user_id == ctx.user_id,
                        InstructorAssignment.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if not accessible:
                    errors.append("Stage not available for analytics.")

        if self.academic_term_id:
            from models.academic_term import AcademicTerm
            term = session.query(AcademicTerm).filter(AcademicTerm.id == self.academic_term_id).first()
            if not term:
                errors.append("Selected term not found.")
            elif ctx and ctx.role != "administrator":
                from models.assessment import Assessment
                from models.instructor_assignment import InstructorAssignment
                from models.material import Material
                accessible = (
                    session.query(Material.id)
                    .filter(Material.academic_term_id == self.academic_term_id)
                    .join(Assessment, Assessment.material_id == Material.id)
                    .join(InstructorAssignment, InstructorAssignment.assessment_id == Assessment.id)
                    .filter(
                        InstructorAssignment.instructor_user_id == ctx.user_id,
                        InstructorAssignment.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if not accessible:
                    errors.append("Term not available for analytics.")

        if self.academic_year_id:
            from models.academic_year import AcademicYear
            yr = session.query(AcademicYear).filter(AcademicYear.id == self.academic_year_id).first()
            if not yr:
                errors.append("Selected academic year not found.")
            elif ctx and ctx.role != "administrator":
                from models.assessment import Assessment
                from models.instructor_assignment import InstructorAssignment
                from models.material import Material
                accessible = (
                    session.query(Material.id)
                    .filter(Material.academic_year_id == self.academic_year_id)
                    .join(Assessment, Assessment.material_id == Material.id)
                    .join(InstructorAssignment, InstructorAssignment.assessment_id == Assessment.id)
                    .filter(
                        InstructorAssignment.instructor_user_id == ctx.user_id,
                        InstructorAssignment.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if not accessible:
                    errors.append("Academic year not available for analytics.")

        # Instructor cannot request another instructor's user ID
        if ctx and ctx.role != "administrator" and self.instructor_user_id:
            if self.instructor_user_id != ctx.user_id:
                errors.append("Instructor may only request their own analytics.")

        # Instructor filter validation for assigned assessments
        if ctx and ctx.role != "administrator" and self.assessment_id:
            from models.instructor_assignment import InstructorAssignment

            assignment = (
                session.query(InstructorAssignment)
                .filter(
                    InstructorAssignment.instructor_user_id == ctx.user_id,
                    InstructorAssignment.assessment_id == self.assessment_id,
                    InstructorAssignment.is_active == True,  # noqa: E712
                )
                .first()
            )
            if not assignment:
                # Return generic error — don't reveal whether the ID exists
                errors.append("Assessment not available for analytics.")

        return errors

    def is_empty(self) -> bool:
        """Return True if no meaningful filters are applied."""
        return not any(
            [
                self.material_id,
                self.assessment_id,
                self.instructor_user_id,
                self.date_from,
                self.date_to,
                self.submission_statuses,
                self.grading_statuses,
                self.question_id,
                self.department_id,
                self.academic_stage_id,
                self.academic_term_id,
                self.academic_year_id,
            ]
        )

    def summary(self) -> str:
        """Return a human-readable filter summary."""
        parts: list[str] = []
        if self.material_id:
            parts.append(f"material={self.material_id[:8]}")
        if self.assessment_id:
            parts.append(f"assessment={self.assessment_id[:8]}")
        if self.instructor_user_id:
            parts.append(f"instructor={self.instructor_user_id[:8]}")
        if self.date_from:
            parts.append(f"from={self.date_from.date()}")
        if self.date_to:
            parts.append(f"to={self.date_to.date()}")
        if self.include_archived:
            parts.append("archived=yes")
        if not self.include_finalized:
            parts.append("finalized=no")
        if self.department_id:
            parts.append(f"dept={self.department_id[:8]}")
        if self.academic_stage_id:
            parts.append(f"stage={self.academic_stage_id[:8]}")
        if self.academic_term_id:
            parts.append(f"term={self.academic_term_id[:8]}")
        if self.academic_year_id:
            parts.append(f"year={self.academic_year_id[:8]}")
        return ", ".join(parts) if parts else "none"


def authorized_assessment_ids(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter | None = None,
) -> list[str]:
    """Return assessment IDs that the caller is authorized to view.

    Parameters
    ----------
    session : Session
        Database session.
    ctx : AuthContext | None
        Authorization context.
    filter_obj : AnalyticsFilter | None
        Optional filter to narrow results.

    Returns
    -------
    list[str]
        Authorized assessment IDs.
    """
    from models.assessment import Assessment
    from models.material import Material

    query = session.query(Assessment.id)

    # Apply classification filters through material join
    if filter_obj:
        if filter_obj.material_id:
            query = query.filter(Assessment.material_id == filter_obj.material_id)
        if filter_obj.assessment_id:
            query = query.filter(Assessment.id == filter_obj.assessment_id)
        if any([filter_obj.department_id, filter_obj.academic_stage_id,
                filter_obj.academic_term_id, filter_obj.academic_year_id]):
            query = query.join(Material, Assessment.material_id == Material.id)
            if filter_obj.department_id:
                query = query.filter(Material.department_id == filter_obj.department_id)
            if filter_obj.academic_stage_id:
                query = query.filter(Material.academic_stage_id == filter_obj.academic_stage_id)
            if filter_obj.academic_term_id:
                query = query.filter(Material.academic_term_id == filter_obj.academic_term_id)
            if filter_obj.academic_year_id:
                query = query.filter(Material.academic_year_id == filter_obj.academic_year_id)
    else:
        if filter_obj and filter_obj.material_id:
            query = query.filter(Assessment.material_id == filter_obj.material_id)
        if filter_obj and filter_obj.assessment_id:
            query = query.filter(Assessment.id == filter_obj.assessment_id)

    if ctx and ctx.role == "administrator":
        # Admin sees all
        pass
    elif ctx and ctx.user_id:
        # Instructor sees only actively assigned assessments
        from models.instructor_assignment import InstructorAssignment

        assigned_ids = (
            session.query(InstructorAssignment.assessment_id)
            .filter(
                InstructorAssignment.instructor_user_id == ctx.user_id,
                InstructorAssignment.is_active == True,  # noqa: E712
            )
            .subquery()
        )
        query = query.filter(Assessment.id.in_(session.query(assigned_ids.c.assessment_id)))
    else:
        # Unauthenticated — no access
        return []

    return [row[0] for row in query.all()]
