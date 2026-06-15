# Academic Anonymous Grader — Material Service
"""CRUD operations for academic materials."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.material import Material
from services.exceptions import (
    DuplicateMaterialError,
    MaterialNotFoundError,
    MaterialValidationError,
)
from services.validation import normalize_optional_text, normalize_required_text


@dataclass
class MaterialResult:
    """Typed result for material operations."""
    id: str
    name: str
    code: str | None
    academic_year: str | None
    stage: str | None
    department: str | None
    notes: str | None
    is_archived: bool
    assessment_count: int
    created_at: str
    updated_at: str | None


def _material_to_result(m: Material, assessment_count: int = 0) -> MaterialResult:
    return MaterialResult(
        id=m.id,
        name=m.name,
        code=m.code,
        academic_year=m.academic_year,
        stage=m.stage,
        department=m.department,
        notes=m.notes,
        is_archived=m.is_archived,
        assessment_count=assessment_count or len(m.assessments),
        created_at=m.created_at.isoformat() if m.created_at else "",
        updated_at=m.updated_at.isoformat() if m.updated_at else None,
    )


def exact_duplicate_exists(
    session: Session, name: str, academic_year: str | None = None,
    stage: str | None = None, department: str | None = None,
    exclude_id: str | None = None,
) -> bool:
    """Check if an active material with the same key fields already exists."""
    query = session.query(Material).filter(
        Material.name == name,
        Material.is_archived == False,  # noqa: E712
    )
    if academic_year:
        query = query.filter(Material.academic_year == academic_year)
    if stage:
        query = query.filter(Material.stage == stage)
    if department:
        query = query.filter(Material.department == department)
    if exclude_id:
        query = query.filter(Material.id != exclude_id)
    return query.first() is not None


def create_material(
    session: Session,
    name: str,
    code: str | None = None,
    academic_year: str | None = None,
    stage: str | None = None,
    department: str | None = None,
    notes: str | None = None,
) -> MaterialResult:
    """Create a new academic material.

    Raises
    ------
    MaterialValidationError
        If validation fails.
    DuplicateMaterialError
        If an exact duplicate active material exists.
    """
    try:
        clean_name = normalize_required_text(name, max_length=200)
    except ValueError as exc:
        raise MaterialValidationError(str(exc)) from exc

    clean_code = normalize_optional_text(code, max_length=50)
    clean_year = normalize_optional_text(academic_year, max_length=30)
    clean_stage = normalize_optional_text(stage, max_length=100)
    clean_dept = normalize_optional_text(department, max_length=200)
    clean_notes = normalize_optional_text(notes)

    if exact_duplicate_exists(
        session, clean_name, clean_year, clean_stage, clean_dept
    ):
        raise DuplicateMaterialError(
            "An active material with this name, academic year, stage, and department already exists"
        )

    material = Material(
        name=clean_name,
        code=clean_code,
        academic_year=clean_year,
        stage=clean_stage,
        department=clean_dept,
        notes=clean_notes,
    )
    session.add(material)
    session.flush()
    return _material_to_result(material)


def get_material(session: Session, material_id: str) -> MaterialResult:
    """Get a material by ID.

    Raises MaterialNotFoundError if not found.
    """
    m = session.query(Material).filter(Material.id == material_id).first()
    if not m:
        raise MaterialNotFoundError(f"Material {material_id} not found")
    return _material_to_result(m, assessment_count=len(m.assessments))


def list_materials(
    session: Session,
    include_archived: bool = False,
    search_query: str | None = None,
) -> list[MaterialResult]:
    """List materials, optionally including archived and filtering by search."""
    query = session.query(Material)
    if not include_archived:
        query = query.filter(Material.is_archived == False)  # noqa: E712
    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(Material.name.ilike(pattern), Material.code.ilike(pattern))
        )
    query = query.order_by(Material.is_archived, Material.name)
    materials = query.all()
    return [_material_to_result(m, assessment_count=len(m.assessments)) for m in materials]


def update_material(
    session: Session,
    material_id: str,
    name: str | None = None,
    code: str | None = None,
    academic_year: str | None = None,
    stage: str | None = None,
    department: str | None = None,
    notes: str | None = None,
) -> MaterialResult:
    """Update an existing material.

    Raises MaterialNotFoundError if not found.
    """
    m = session.query(Material).filter(Material.id == material_id).first()
    if not m:
        raise MaterialNotFoundError(f"Material {material_id} not found")

    if name is not None:
        try:
            m.name = normalize_required_text(name, max_length=200)
        except ValueError as exc:
            raise MaterialValidationError(str(exc)) from exc

    if code is not None:
        m.code = normalize_optional_text(code, max_length=50)
    if academic_year is not None:
        m.academic_year = normalize_optional_text(academic_year, max_length=30)
    if stage is not None:
        m.stage = normalize_optional_text(stage, max_length=100)
    if department is not None:
        m.department = normalize_optional_text(department, max_length=200)
    if notes is not None:
        m.notes = normalize_optional_text(notes)

    # Check duplicate after changes
    if m.name and exact_duplicate_exists(
        session, m.name, m.academic_year, m.stage, m.department,
        exclude_id=material_id,
    ):
        raise DuplicateMaterialError(
            "An active material with this name, academic year, stage, and department already exists"
        )

    session.flush()
    return _material_to_result(m, assessment_count=len(m.assessments))


def archive_material(session: Session, material_id: str) -> MaterialResult:
    """Archive a material (soft delete)."""
    m = session.query(Material).filter(Material.id == material_id).first()
    if not m:
        raise MaterialNotFoundError(f"Material {material_id} not found")
    m.is_archived = True
    session.flush()
    return _material_to_result(m, assessment_count=len(m.assessments))


def restore_material(session: Session, material_id: str) -> MaterialResult:
    """Restore an archived material."""
    m = session.query(Material).filter(Material.id == material_id).first()
    if not m:
        raise MaterialNotFoundError(f"Material {material_id} not found")
    m.is_archived = False
    session.flush()
    return _material_to_result(m, assessment_count=len(m.assessments))


def active_material_count(session: Session) -> int:
    """Return count of active (non-archived) materials."""
    return session.query(func.count(Material.id)).filter(
        Material.is_archived == False  # noqa: E712
    ).scalar() or 0


def archived_material_count(session: Session) -> int:
    """Return count of archived materials."""
    return session.query(func.count(Material.id)).filter(
        Material.is_archived == True  # noqa: E712
    ).scalar() or 0
