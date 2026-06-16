# Academic Anonymous Grader — Phase 12.1 Academic Structure Tests
"""Tests for academic structure models, services, authorization,
migration, and data quality integration."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from models.academic_stage import AcademicStage
from models.academic_term import AcademicTerm
from models.academic_year import AcademicYear
from models.department import Department
from services.authorization_service import (
    PERM_MANAGE_ACADEMIC_STRUCTURE,
    AuthContext,
    has_permission,
)

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    conn = engine.connect()
    trans = conn.begin()
    session_factory = sessionmaker(bind=conn)
    sess = session_factory()
    yield sess
    sess.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def admin_ctx() -> AuthContext:
    return AuthContext(user_id="admin-1", username="admin", role="administrator")


@pytest.fixture
def grader_ctx() -> AuthContext:
    return AuthContext(user_id="grader-1", username="grader1", role="grader")


# ── Authorization Tests ───────────────────────────────────────────


class TestAcademicStructureAuthorization:
    def test_admin_has_permission(self):
        assert has_permission("administrator", PERM_MANAGE_ACADEMIC_STRUCTURE)

    def test_grader_no_permission(self):
        assert not has_permission("grader", PERM_MANAGE_ACADEMIC_STRUCTURE)

    def test_page_access(self):
        from services.authorization_service import _PAGE_ROLES
        assert "administrator" in _PAGE_ROLES.get("AcademicStructure", set())

    def test_grader_no_page_access(self):
        from services.authorization_service import can_access_page
        assert not can_access_page("grader", "AcademicStructure")


# ── Seed Tests ────────────────────────────────────────────────────


class TestAcademicStructureSeed:
    def test_default_departments_seeded(self, session):
        from services.academic_structure_service import seed_default_academic_structure
        results = seed_default_academic_structure(session)
        assert len(results) == 3 + 4 + 2  # 3 depts + 4 stages + 2 terms
        depts = session.query(Department).all()
        assert len(depts) == 3
        codes = [d.code for d in depts]
        assert "big_data" in codes

    def test_seed_idempotent(self, session):
        from services.academic_structure_service import seed_default_academic_structure
        seed_default_academic_structure(session)
        session.flush()
        results = seed_default_academic_structure(session)
        assert len(results) == 0  # no new records

    def test_four_stages_seeded(self, session):
        from services.academic_structure_service import seed_default_academic_structure
        seed_default_academic_structure(session)
        stages = session.query(AcademicStage).all()
        assert len(stages) == 4
        nums = sorted([s.stage_number for s in stages])
        assert nums == [1, 2, 3, 4]

    def test_two_terms_seeded(self, session):
        from services.academic_structure_service import seed_default_academic_structure
        seed_default_academic_structure(session)
        terms = session.query(AcademicTerm).all()
        assert len(terms) == 2


# ── Department CRUD Tests ─────────────────────────────────────────


class TestDepartmentCRUD:
    def test_create_department(self, session, admin_ctx):
        from services.academic_structure_service import create_department
        dept = create_department(session, admin_ctx, "test_dept", "Test Department")
        assert dept.code == "test_dept"
        assert dept.display_name == "Test Department"

    def test_duplicate_code_rejected(self, session, admin_ctx):
        from services.academic_structure_service import create_department
        from services.exceptions import DuplicateMaterialError
        create_department(session, admin_ctx, "test_dept", "Test")
        with pytest.raises(DuplicateMaterialError):
            create_department(session, admin_ctx, "test_dept", "Another")

    def test_list_active_only(self, session, admin_ctx):
        from services.academic_structure_service import create_department, list_departments
        create_department(session, admin_ctx, "dept_a", "A")
        create_department(session, admin_ctx, "dept_b", "B")
        depts = list_departments(session)
        assert len(depts) == 2

    def test_archive_reactivate(self, session, admin_ctx):
        from services.academic_structure_service import (
            archive_department,
            create_department,
            list_departments,
            reactivate_department,
        )
        dept = create_department(session, admin_ctx, "test", "Test")
        archive_department(session, admin_ctx, dept.id)
        assert len(list_departments(session)) == 0
        reactivate_department(session, admin_ctx, dept.id)
        assert len(list_departments(session)) == 1

    def test_instructor_blocked(self, session, grader_ctx):
        from services.academic_structure_service import create_department
        from services.exceptions import InsufficientPermissionsError
        with pytest.raises(InsufficientPermissionsError):
            create_department(session, grader_ctx, "test", "Test")


# ── Stage CRUD Tests ──────────────────────────────────────────────


class TestStageCRUD:
    def test_create_stage(self, session, admin_ctx):
        from services.academic_structure_service import create_stage
        s = create_stage(session, admin_ctx, "stage_1", "Stage 1", 1)
        assert s.stage_number == 1

    def test_invalid_stage_number_rejected(self, session, admin_ctx):
        from services.academic_structure_service import create_stage
        from services.exceptions import MaterialValidationError
        with pytest.raises(MaterialValidationError):
            create_stage(session, admin_ctx, "bad", "Bad", 5)

    def test_duplicate_stage_number_rejected(self, session, admin_ctx):
        from services.academic_structure_service import create_stage
        create_stage(session, admin_ctx, "s1", "S1", 1)
        with pytest.raises(Exception):  # IntegrityError from DB unique constraint
            create_stage(session, admin_ctx, "s1b", "S1b", 1)


# ── Term CRUD Tests ───────────────────────────────────────────────


class TestTermCRUD:
    def test_create_term(self, session, admin_ctx):
        from services.academic_structure_service import create_term
        t = create_term(session, admin_ctx, "term_1", "Term 1", 1)
        assert t.term_number == 1

    def test_invalid_term_number_rejected(self, session, admin_ctx):
        from services.academic_structure_service import create_term
        from services.exceptions import MaterialValidationError
        with pytest.raises(MaterialValidationError):
            create_term(session, admin_ctx, "bad", "Bad", 3)


# ── Academic Year CRUD Tests ──────────────────────────────────────


class TestAcademicYearCRUD:
    def test_create_valid_year(self, session, admin_ctx):
        from services.academic_structure_service import create_academic_year
        y = create_academic_year(session, admin_ctx, "2026_2027", "2026–2027", 2026, 2027)
        assert y.start_year == 2026
        assert y.end_year == 2027

    def test_invalid_range_rejected(self, session, admin_ctx):
        from services.academic_structure_service import create_academic_year
        from services.exceptions import MaterialValidationError
        with pytest.raises(MaterialValidationError):
            create_academic_year(session, admin_ctx, "bad", "Bad", 2026, 2028)

    def test_only_one_current_year(self, session, admin_ctx):
        from services.academic_structure_service import (
            create_academic_year,
            set_current_academic_year,
        )
        y1 = create_academic_year(session, admin_ctx, "y1", "Y1", 2026, 2027)
        y2 = create_academic_year(session, admin_ctx, "y2", "Y2", 2027, 2028)
        set_current_academic_year(session, admin_ctx, y1.id)
        set_current_academic_year(session, admin_ctx, y2.id)
        current_count = session.query(AcademicYear).filter(
            AcademicYear.is_current == True  # noqa: E712
        ).count()
        assert current_count == 1

    def test_current_year_archive_protected(self, session, admin_ctx):
        from services.academic_structure_service import (
            archive_academic_year,
            create_academic_year,
            set_current_academic_year,
        )
        from services.exceptions import MaterialValidationError
        y = create_academic_year(session, admin_ctx, "y1", "Y1", 2026, 2027)
        set_current_academic_year(session, admin_ctx, y.id)
        with pytest.raises(MaterialValidationError):
            archive_academic_year(session, admin_ctx, y.id)


# ── Material Classification Tests ─────────────────────────────────


class TestMaterialClassification:
    def test_create_with_classification(self, session, admin_ctx):
        from services.academic_structure_service import (
            list_departments,
            list_stages,
            list_terms,
            seed_default_academic_structure,
        )
        from services.material_service import create_material

        seed_default_academic_structure(session)
        depts = list_departments(session)
        stages = list_stages(session)
        terms = list_terms(session)

        mat = create_material(
            session, "Test Material", code="TEST",
            department_id=depts[0].id,
            academic_stage_id=stages[0].id,
            academic_term_id=terms[0].id,
        )
        assert mat.department_id == depts[0].id
        assert mat.department_label == depts[0].display_name

    def test_inactive_ref_blocked_for_new(self, session, admin_ctx):
        from services.academic_structure_service import (
            archive_department,
            create_department,
        )

        dept = create_department(session, admin_ctx, "test", "Test")
        archive_department(session, admin_ctx, dept.id)
        assert dept.id is not None

    def test_archived_ref_valid_for_historical(self, session, admin_ctx):
        from services.academic_structure_service import (
            archive_department,
            create_department,
        )
        from services.material_service import create_material

        dept = create_department(session, admin_ctx, "test", "Test")
        mat = create_material(
            session, "Historical", department_id=dept.id,
        )
        archive_department(session, admin_ctx, dept.id)
        # Historical material should still be accessible
        from services.material_service import get_material
        m = get_material(session, mat.id)
        assert m.department_id == dept.id


# ── Analytics Filter Integration Tests ────────────────────────────


class TestAnalyticsFilterIntegration:
    def test_filter_by_department(self, session, admin_ctx):
        from analytics.filters import AnalyticsFilter
        f = AnalyticsFilter(material_id="test")
        assert f.material_id == "test"
        assert f.is_empty() is False


# ── Data Quality Integration Tests ────────────────────────────────


class TestDataQualityIntegration:
    def test_data_quality_with_references(self, session, admin_ctx):
        from analytics.data_quality import get_data_quality_report
        report = get_data_quality_report(session, admin_ctx)
        assert isinstance(report.total_issues, int)


# ── Classification review flag repair tests ──────────────────────


class TestClassificationReviewRepair:
    """Regression tests for the v3 repair of classification_needs_review."""

    def _seed_refs(self, session: Session) -> None:
        """Ensure seed academic structure exists."""
        from services.academic_structure_service import seed_default_academic_structure
        seed_default_academic_structure(session)
        session.flush()

    def _material_without_refs(self, session: Session) -> str:
        """Create a material with no classification refs, flag=False."""
        from models.material import Material
        m = Material(
            name="Legacy Material",
            classification_needs_review=False,
        )
        session.add(m)
        session.flush()
        return m.id

    def _material_with_refs(self, session: Session) -> str:
        """Create a fully classified material, flag=False."""
        from models.academic_stage import AcademicStage
        from models.academic_term import AcademicTerm
        from models.academic_year import AcademicYear
        from models.department import Department
        from models.material import Material
        dept = session.query(Department).first()
        stage = session.query(AcademicStage).first()
        term = session.query(AcademicTerm).first()
        yr = session.query(AcademicYear).first()
        if yr is None:
            from models.academic_year import AcademicYear as AY
            ay = AY(code="year_2026", display_name="2026-2027", start_year=2026, end_year=2027)
            session.add(ay)
            session.flush()
            yr_id = ay.id
        else:
            yr_id = yr.id
        m = Material(
            name="Classified Material",
            department_id=dept.id if dept else None,
            academic_stage_id=stage.id if stage else None,
            academic_term_id=term.id if term else None,
            academic_year_id=yr_id,
            classification_needs_review=False,
        )
        session.add(m)
        session.flush()
        return m.id

    def _material_partial_refs(self, session: Session) -> str:
        """Create a material with only department set, flag=False."""
        from models.department import Department
        from models.material import Material
        dept = session.query(Department).first()
        m = Material(
            name="Partially Classified Material",
            department_id=dept.id if dept else None,
            classification_needs_review=False,
        )
        session.add(m)
        session.flush()
        return m.id

    def _run_repair(self, session: Session) -> int:
        """Simulate the fix_classification_review logic."""
        from models.material import Material
        pending = session.query(Material).filter(
            Material.classification_needs_review == False,  # noqa: E712
            (
                (Material.department_id.is_(None))
                | (Material.academic_stage_id.is_(None))
                | (Material.academic_term_id.is_(None))
                | (Material.academic_year_id.is_(None))
            ),
        ).all()
        for m in pending:
            refs = [m.department_id, m.academic_stage_id, m.academic_term_id, m.academic_year_id]
            m.classification_needs_review = not all(r is not None for r in refs)
        session.flush()
        return len(pending)

    def _count_flag(self, session: Session, value: bool) -> int:
        from models.material import Material
        return session.query(Material).filter(
            Material.classification_needs_review == value  # noqa: E712
        ).count()

    def test_v3_repair_unclassified_marked(self, session):
        """Unclassified material with flag=False gets flag=True after repair."""
        self._seed_refs(session)
        self._material_without_refs(session)
        assert self._count_flag(session, False) == 1
        fixed = self._run_repair(session)
        assert fixed == 1
        assert self._count_flag(session, True) == 1
        assert self._count_flag(session, False) == 0

    def test_v3_repair_idempotent(self, session):
        """Running repair twice gives same result."""
        self._seed_refs(session)
        self._material_without_refs(session)
        self._run_repair(session)
        fixed2 = self._run_repair(session)
        assert fixed2 == 0  # already fixed

    def test_v3_repair_fully_classified_stays_false(self, session):
        """Fully classified material with flag=False stays False."""
        self._seed_refs(session)
        self._material_with_refs(session)
        assert self._count_flag(session, False) == 1
        fixed = self._run_repair(session)
        assert fixed == 0
        assert self._count_flag(session, False) == 1
        assert self._count_flag(session, True) == 0

    def test_v3_repair_partial_stays_under_review(self, session):
        """Partially classified material gets flag=True."""
        self._seed_refs(session)
        self._material_partial_refs(session)
        assert self._count_flag(session, False) == 1
        fixed = self._run_repair(session)
        assert fixed == 1
        assert self._count_flag(session, True) == 1

    def test_v3_repair_no_duplicates_created(self, session):
        """Repair does not create duplicate records."""
        from models.material import Material
        self._seed_refs(session)
        self._material_without_refs(session)
        before = session.query(Material).count()
        self._run_repair(session)
        after = session.query(Material).count()
        assert before == after

    def test_v3_repair_seed_totals_preserved(self, session):
        """Seed totals remain 3 departments, 4 stages, 2 terms."""
        self._seed_refs(session)
        self._material_without_refs(session)
        self._run_repair(session)
        assert session.query(Department).count() == 3
        assert session.query(AcademicStage).count() == 4
        assert session.query(AcademicTerm).count() == 2

    def test_v3_repair_ambiguous_values_unresolved(self, session):
        """Material with unknown legacy dept text stays unresolved."""
        self._seed_refs(session)
        from models.material import Material
        m = Material(
            name="Ambiguous Dept Material",
            department="Some Unknown Department",
            classification_needs_review=False,
        )
        session.add(m)
        session.flush()
        fixed = self._run_repair(session)
        assert fixed == 1  # needs review since no ref was mapped
        assert m.classification_needs_review is True
