# Academic Anonymous Grader — Material Service Tests
"""Tests for services/material_service.py."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from services.exceptions import DuplicateMaterialError, MaterialNotFoundError, MaterialValidationError
from services.material_service import (
    active_material_count,
    archive_material,
    archived_material_count,
    create_material,
    get_material,
    list_materials,
    restore_material,
    update_material,
)


class TestCreateMaterial:
    """Material creation tests."""

    def test_create_valid_material(self, session: Session) -> None:
        result = create_material(session, name="Object-Oriented Programming")
        session.flush()
        assert result.name == "Object-Oriented Programming"
        assert result.is_archived is False
        assert result.id is not None

    def test_reject_blank_name(self, session: Session) -> None:
        with pytest.raises(MaterialValidationError, match="must not be blank"):
            create_material(session, name="   ")

    def test_trim_whitespace(self, session: Session) -> None:
        result = create_material(session, name="  Course  Name  ")
        session.flush()
        assert result.name == "Course  Name"

    def test_blank_optional_converted_to_none(self, session: Session) -> None:
        result = create_material(
            session, name="Test", code="", academic_year="",
            stage="  ", department="", notes="   ",
        )
        session.flush()
        assert result.code is None
        assert result.academic_year is None
        assert result.stage is None
        assert result.department is None
        assert result.notes is None

    def test_preserve_arabic_text(self, session: Session) -> None:
        result = create_material(session, name="برمجة كائنية التوجه")
        session.flush()
        assert result.name == "برمجة كائنية التوجه"

    def test_duplicate_active_material_blocked(self, session: Session) -> None:
        create_material(session, name="Math 101", academic_year="2025")
        session.flush()
        with pytest.raises(DuplicateMaterialError):
            create_material(session, name="Math 101", academic_year="2025")

    def test_same_name_different_year_allowed(self, session: Session) -> None:
        create_material(session, name="Math 101", academic_year="2025")
        session.flush()
        result = create_material(session, name="Math 101", academic_year="2026")
        session.flush()
        assert result.name == "Math 101"
        assert result.academic_year == "2026"


class TestArchiveRestore:
    """Archive and restore tests."""

    def test_archive_material(self, session: Session) -> None:
        result = create_material(session, name="To Archive")
        session.flush()
        archived = archive_material(session, result.id)
        session.flush()
        assert archived.is_archived is True

    def test_restore_material(self, session: Session) -> None:
        result = create_material(session, name="To Restore")
        session.flush()
        archive_material(session, result.id)
        session.flush()
        restored = restore_material(session, result.id)
        session.flush()
        assert restored.is_archived is False

    def test_archived_hidden_from_active_list(self, session: Session) -> None:
        create_material(session, name="Active One")
        result = create_material(session, name="Archived One")
        session.flush()
        archive_material(session, result.id)
        session.flush()
        active = list_materials(session, include_archived=False)
        names = [m.name for m in active]
        assert "Active One" in names
        assert "Archived One" not in names

    def test_archived_included_when_requested(self, session: Session) -> None:
        create_material(session, name="Active")
        m2 = create_material(session, name="Archived")
        session.flush()
        archive_material(session, m2.id)
        session.flush()
        all_mats = list_materials(session, include_archived=True)
        assert len(all_mats) == 2


class TestSearchMaterial:
    """Material search tests."""

    def test_search_by_name(self, session: Session) -> None:
        create_material(session, name="Introduction to Python")
        create_material(session, name="Advanced Java")
        session.flush()
        results = list_materials(session, search_query="Python")
        assert len(results) == 1
        assert results[0].name == "Introduction to Python"

    def test_search_by_code(self, session: Session) -> None:
        create_material(session, name="Course", code="CS101")
        session.flush()
        results = list_materials(session, search_query="CS101")
        assert len(results) == 1


class TestUpdateMaterial:
    """Material update tests."""

    def test_update_material(self, session: Session) -> None:
        result = create_material(session, name="Original")
        session.flush()
        updated = update_material(session, result.id, name="Updated")
        assert updated.name == "Updated"

    def test_missing_material_raises_error(self, session: Session) -> None:
        with pytest.raises(MaterialNotFoundError):
            get_material(session, "nonexistent-id")

    def test_update_nonexistent_raises_error(self, session: Session) -> None:
        with pytest.raises(MaterialNotFoundError):
            update_material(session, "bad-id", name="New")


class TestCounts:
    """Material count tests."""

    def test_active_count(self, session: Session) -> None:
        create_material(session, name="A")
        result = create_material(session, name="B")
        session.flush()
        assert active_material_count(session) == 2
        archive_material(session, result.id)
        session.flush()
        assert active_material_count(session) == 1

    def test_archived_count(self, session: Session) -> None:
        m = create_material(session, name="To Archive")
        session.flush()
        assert archived_material_count(session) == 0
        archive_material(session, m.id)
        session.flush()
        assert archived_material_count(session) == 1
