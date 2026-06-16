# Academic Anonymous Grader — Academic Structure Service
"""Service layer for managing academic reference data.

All mutation functions require Administrator AuthContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from models.academic_stage import AcademicStage
from models.academic_term import AcademicTerm
from models.academic_year import AcademicYear
from models.department import Department
from models.material import Material
from services.authorization_service import AuthContext, require_role_is
from services.exceptions import (
    DuplicateMaterialError,
    InsufficientPermissionsError,
    MaterialValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ── Result types ──────────────────────────────────────────────────


@dataclass(frozen=True)
class DepartmentResult:
    id: str
    code: str
    display_name: str
    abbreviation: str | None
    description: str | None
    sort_order: int
    is_active: bool
    material_count: int = 0


@dataclass(frozen=True)
class StageResult:
    id: str
    code: str
    display_name: str
    stage_number: int
    sort_order: int
    is_active: bool
    material_count: int = 0


@dataclass(frozen=True)
class TermResult:
    id: str
    code: str
    display_name: str
    term_number: int
    sort_order: int
    is_active: bool
    material_count: int = 0


@dataclass(frozen=True)
class AcademicYearResult:
    id: str
    code: str
    display_name: str
    start_year: int
    end_year: int
    is_active: bool
    is_current: bool
    sort_order: int
    material_count: int = 0


# ── Authorization helper ──────────────────────────────────────────


def _require_admin(ctx: AuthContext | None) -> None:
    if ctx is None or not ctx.user_id:
        raise InsufficientPermissionsError("Authentication required.")
    require_role_is(ctx, "administrator")


# ── Seed data ─────────────────────────────────────────────────────


SEED_DEPARTMENTS: list[dict[str, Any]] = [
    {"code": "big_data", "display_name": "Big Data", "sort_order": 1},
    {"code": "medical_applications", "display_name": "Medical Applications", "sort_order": 2},
    {"code": "engineering_applications", "display_name": "Engineering Applications", "sort_order": 3},
]

SEED_STAGES: list[dict[str, Any]] = [
    {"code": "stage_1", "display_name": "Stage 1", "stage_number": 1, "sort_order": 1},
    {"code": "stage_2", "display_name": "Stage 2", "stage_number": 2, "sort_order": 2},
    {"code": "stage_3", "display_name": "Stage 3", "stage_number": 3, "sort_order": 3},
    {"code": "stage_4", "display_name": "Stage 4", "stage_number": 4, "sort_order": 4},
]

SEED_TERMS: list[dict[str, Any]] = [
    {"code": "term_1", "display_name": "Term 1", "term_number": 1, "sort_order": 1},
    {"code": "term_2", "display_name": "Term 2", "term_number": 2, "sort_order": 2},
]


def seed_default_academic_structure(session: Session) -> list[str]:
    """Seed default Departments, Stages, and Terms idempotently.

    Returns list of descriptions of what was seeded.
    """
    results: list[str] = []

    for seed_dept in SEED_DEPARTMENTS:
        existing = session.query(Department).filter(Department.code == seed_dept["code"]).first()
        if not existing:
            dept = Department(
                code=seed_dept["code"],
                display_name=seed_dept["display_name"],
                sort_order=seed_dept["sort_order"],
            )
            session.add(dept)
            results.append(f"Department '{seed_dept['display_name']}' created")
        session.flush()

    for seed_stage in SEED_STAGES:
        existing = session.query(AcademicStage).filter(AcademicStage.code == seed_stage["code"]).first()  # type: ignore[assignment]
        if not existing:
            stage = AcademicStage(
                code=seed_stage["code"],
                display_name=seed_stage["display_name"],
                stage_number=seed_stage["stage_number"],
                sort_order=seed_stage["sort_order"],
            )
            session.add(stage)
            results.append(f"Stage '{seed_stage['display_name']}' created")
        session.flush()

    for seed_term in SEED_TERMS:
        existing = session.query(AcademicTerm).filter(AcademicTerm.code == seed_term["code"]).first()  # type: ignore[assignment]
        if not existing:
            term = AcademicTerm(
                code=seed_term["code"],
                display_name=seed_term["display_name"],
                term_number=seed_term["term_number"],
                sort_order=seed_term["sort_order"],
            )
            session.add(term)
            results.append(f"Term '{seed_term['display_name']}' created")
        session.flush()

    return results


# ── Department functions ──────────────────────────────────────────


def _dept_to_result(d: Department, material_count: int = 0) -> DepartmentResult:
    return DepartmentResult(
        id=d.id, code=d.code, display_name=d.display_name,
        abbreviation=d.abbreviation, description=d.description,
        sort_order=d.sort_order, is_active=d.is_active,
        material_count=material_count,
    )


def list_departments(
    session: Session,
    include_inactive: bool = False,
) -> list[DepartmentResult]:
    query = session.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active == True)  # noqa: E712
    query = query.order_by(Department.sort_order, Department.display_name)
    return [_dept_to_result(d) for d in query.all()]


def create_department(
    session: Session, ctx: AuthContext | None,
    code: str, display_name: str,
    abbreviation: str | None = None,
    description: str | None = None,
    sort_order: int = 0,
) -> DepartmentResult:
    """Create a new department. Administrator only."""
    _require_admin(ctx)
    existing = session.query(Department).filter(Department.code == code).first()
    if existing:
        raise DuplicateMaterialError(f"Department with code '{code}' already exists.")
    dept = Department(
        code=code, display_name=display_name,
        abbreviation=abbreviation or None,
        description=description or None,
        sort_order=sort_order,
        created_by_user_id=ctx.user_id if ctx else None,
    )
    session.add(dept)
    session.flush()
    return _dept_to_result(dept)


def update_department(
    session: Session, ctx: AuthContext | None,
    department_id: str,
    display_name: str | None = None,
    abbreviation: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
) -> DepartmentResult:
    _require_admin(ctx)
    dept = session.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise MaterialValidationError("Department not found.")
    if display_name is not None:
        dept.display_name = display_name
    if abbreviation is not None:
        dept.abbreviation = abbreviation or None
    if description is not None:
        dept.description = description or None
    if sort_order is not None:
        dept.sort_order = sort_order
    dept.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _dept_to_result(dept)


def archive_department(
    session: Session, ctx: AuthContext | None, department_id: str,
) -> DepartmentResult:
    _require_admin(ctx)
    dept = session.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise MaterialValidationError("Department not found.")
    dept.is_active = False
    dept.archived_at = datetime.now(UTC).isoformat()
    dept.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _dept_to_result(dept)


def reactivate_department(
    session: Session, ctx: AuthContext | None, department_id: str,
) -> DepartmentResult:
    _require_admin(ctx)
    dept = session.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise MaterialValidationError("Department not found.")
    dept.is_active = True
    dept.archived_at = None
    dept.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _dept_to_result(dept)


# ── Stage functions ────────────────────────────────────────────────


def _stage_to_result(s: AcademicStage, material_count: int = 0) -> StageResult:
    return StageResult(
        id=s.id, code=s.code, display_name=s.display_name,
        stage_number=s.stage_number, sort_order=s.sort_order,
        is_active=s.is_active, material_count=material_count,
    )


def list_stages(
    session: Session, include_inactive: bool = False,
) -> list[StageResult]:
    query = session.query(AcademicStage)
    if not include_inactive:
        query = query.filter(AcademicStage.is_active == True)  # noqa: E712
    query = query.order_by(AcademicStage.sort_order, AcademicStage.display_name)
    return [_stage_to_result(s) for s in query.all()]


def create_stage(
    session: Session, ctx: AuthContext | None,
    code: str, display_name: str,
    stage_number: int, sort_order: int = 0,
) -> StageResult:
    _require_admin(ctx)
    if stage_number < 1 or stage_number > 4:
        raise MaterialValidationError("Stage number must be between 1 and 4.")
    existing = session.query(AcademicStage).filter(
        AcademicStage.code == code
    ).first()
    if existing:
        raise DuplicateMaterialError(f"Stage with code '{code}' already exists.")
    stage = AcademicStage(
        code=code, display_name=display_name,
        stage_number=stage_number, sort_order=sort_order,
        created_by_user_id=ctx.user_id if ctx else None,
    )
    session.add(stage)
    session.flush()
    return _stage_to_result(stage)


def archive_stage(
    session: Session, ctx: AuthContext | None, stage_id: str,
) -> StageResult:
    _require_admin(ctx)
    stage = session.query(AcademicStage).filter(AcademicStage.id == stage_id).first()
    if not stage:
        raise MaterialValidationError("Stage not found.")
    stage.is_active = False
    stage.archived_at = datetime.now(UTC).isoformat()
    stage.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _stage_to_result(stage)


def reactivate_stage(
    session: Session, ctx: AuthContext | None, stage_id: str,
) -> StageResult:
    _require_admin(ctx)
    stage = session.query(AcademicStage).filter(AcademicStage.id == stage_id).first()
    if not stage:
        raise MaterialValidationError("Stage not found.")
    stage.is_active = True
    stage.archived_at = None
    stage.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _stage_to_result(stage)


# ── Term functions ─────────────────────────────────────────────────


def _term_to_result(t: AcademicTerm, material_count: int = 0) -> TermResult:
    return TermResult(
        id=t.id, code=t.code, display_name=t.display_name,
        term_number=t.term_number, sort_order=t.sort_order,
        is_active=t.is_active, material_count=material_count,
    )


def list_terms(
    session: Session, include_inactive: bool = False,
) -> list[TermResult]:
    query = session.query(AcademicTerm)
    if not include_inactive:
        query = query.filter(AcademicTerm.is_active == True)  # noqa: E712
    query = query.order_by(AcademicTerm.sort_order, AcademicTerm.display_name)
    return [_term_to_result(t) for t in query.all()]


def create_term(
    session: Session, ctx: AuthContext | None,
    code: str, display_name: str,
    term_number: int, sort_order: int = 0,
) -> TermResult:
    _require_admin(ctx)
    if term_number < 1 or term_number > 2:
        raise MaterialValidationError("Term number must be between 1 and 2.")
    existing = session.query(AcademicTerm).filter(
        AcademicTerm.code == code
    ).first()
    if existing:
        raise DuplicateMaterialError(f"Term with code '{code}' already exists.")
    term = AcademicTerm(
        code=code, display_name=display_name,
        term_number=term_number, sort_order=sort_order,
        created_by_user_id=ctx.user_id if ctx else None,
    )
    session.add(term)
    session.flush()
    return _term_to_result(term)


def archive_term(
    session: Session, ctx: AuthContext | None, term_id: str,
) -> TermResult:
    _require_admin(ctx)
    term = session.query(AcademicTerm).filter(AcademicTerm.id == term_id).first()
    if not term:
        raise MaterialValidationError("Term not found.")
    term.is_active = False
    term.archived_at = datetime.now(UTC).isoformat()
    term.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _term_to_result(term)


def reactivate_term(
    session: Session, ctx: AuthContext | None, term_id: str,
) -> TermResult:
    _require_admin(ctx)
    term = session.query(AcademicTerm).filter(AcademicTerm.id == term_id).first()
    if not term:
        raise MaterialValidationError("Term not found.")
    term.is_active = True
    term.archived_at = None
    term.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _term_to_result(term)


# ── Academic Year functions ────────────────────────────────────────


def _year_to_result(y: AcademicYear, material_count: int = 0) -> AcademicYearResult:
    return AcademicYearResult(
        id=y.id, code=y.code, display_name=y.display_name,
        start_year=y.start_year, end_year=y.end_year,
        is_active=y.is_active, is_current=y.is_current,
        sort_order=y.sort_order, material_count=material_count,
    )


def list_academic_years(
    session: Session, include_inactive: bool = False,
) -> list[AcademicYearResult]:
    query = session.query(AcademicYear)
    if not include_inactive:
        query = query.filter(AcademicYear.is_active == True)  # noqa: E712
    query = query.order_by(AcademicYear.sort_order, AcademicYear.display_name)
    return [_year_to_result(y) for y in query.all()]


def create_academic_year(
    session: Session, ctx: AuthContext | None,
    code: str, display_name: str,
    start_year: int, end_year: int | None = None,
    sort_order: int = 0,
) -> AcademicYearResult:
    _require_admin(ctx)
    if end_year is None:
        end_year = start_year + 1
    if end_year != start_year + 1:
        raise MaterialValidationError("end_year must equal start_year + 1.")
    if len(str(start_year)) != 4:
        raise MaterialValidationError("start_year must be a four-digit year.")
    existing = session.query(AcademicYear).filter(
        AcademicYear.code == code
    ).first()
    if existing:
        raise DuplicateMaterialError(f"Academic year with code '{code}' already exists.")
    year = AcademicYear(
        code=code, display_name=display_name,
        start_year=start_year, end_year=end_year,
        sort_order=sort_order,
        created_by_user_id=ctx.user_id if ctx else None,
    )
    session.add(year)
    session.flush()
    return _year_to_result(year)


def set_current_academic_year(
    session: Session, ctx: AuthContext | None, year_id: str,
) -> AcademicYearResult:
    _require_admin(ctx)
    # Clear current flag from all years
    session.query(AcademicYear).filter(
        AcademicYear.is_current == True  # noqa: E712
    ).update({"is_current": False})
    session.flush()
    year = session.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise MaterialValidationError("Academic year not found.")
    year.is_current = True
    year.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _year_to_result(year)


def archive_academic_year(
    session: Session, ctx: AuthContext | None, year_id: str,
) -> AcademicYearResult:
    _require_admin(ctx)
    year = session.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise MaterialValidationError("Academic year not found.")
    if year.is_current:
        raise MaterialValidationError("Cannot archive the current academic year.")
    year.is_active = False
    year.archived_at = datetime.now(UTC).isoformat()
    year.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _year_to_result(year)


def reactivate_academic_year(
    session: Session, ctx: AuthContext | None, year_id: str,
) -> AcademicYearResult:
    _require_admin(ctx)
    year = session.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise MaterialValidationError("Academic year not found.")
    year.is_active = True
    year.archived_at = None
    year.updated_by_user_id = ctx.user_id if ctx else None
    session.flush()
    return _year_to_result(year)


# ── Material classification helpers ────────────────────────────────


def get_classification_options(
    session: Session,
) -> dict[str, Any]:
    """Get active classification options for material forms."""
    return {
        "departments": list_departments(session),
        "stages": list_stages(session),
        "terms": list_terms(session),
        "academic_years": list_academic_years(session),
    }


def get_current_academic_year(
    session: Session,
) -> AcademicYearResult | None:
    """Get the current academic year, if any."""
    year = session.query(AcademicYear).filter(
        AcademicYear.is_current == True  # noqa: E712
    ).first()
    if year:
        return _year_to_result(year)
    return None


def get_reference_usage_counts(
    session: Session,
) -> dict[str, Any]:
    """Get usage counts for all reference records."""
    return {
        "departments": {
            r[0]: r[1] for r in session.query(
                Material.department_id, Material.id.count()
            ).filter(
                Material.department_id.isnot(None)
            ).group_by(Material.department_id).all()
        },
        "stages": {
            r[0]: r[1] for r in session.query(
                Material.academic_stage_id, Material.id.count()
            ).filter(
                Material.academic_stage_id.isnot(None)
            ).group_by(Material.academic_stage_id).all()
        },
        "terms": {
            r[0]: r[1] for r in session.query(
                Material.academic_term_id, Material.id.count()
            ).filter(
                Material.academic_term_id.isnot(None)
            ).group_by(Material.academic_term_id).all()
        },
        "academic_years": {
            r[0]: r[1] for r in session.query(
                Material.academic_year_id, Material.id.count()
            ).filter(
                Material.academic_year_id.isnot(None)
            ).group_by(Material.academic_year_id).all()
        },
    }
