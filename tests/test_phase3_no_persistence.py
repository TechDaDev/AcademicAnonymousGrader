"""Integration test that verifies Phase 3 preview does not persist any data.

Creates a temporary SQLite database, material, assessment, and questions,
parses the sample fixture, and confirms zero records in all persistence tables.
"""

from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from database.session import create_session_factory, session_scope
from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity
from models.submission import Submission
from services.assessment_service import create_assessment
from services.import_preview_service import preview_html_import, reconcile_assessment
from services.material_service import create_material
from services.question_service import create_question, list_questions

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def temp_db() -> Generator[sessionmaker[Session], None, None]:
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_phase3.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        yield factory
        engine.dispose()


class TestPhase3NoPersistence:
    def test_no_records_created_by_preview(self, temp_db: sessionmaker[Session]) -> None:
        factory = temp_db

        # 1. Create material
        with session_scope(factory) as session:
            mat = create_material(
                session, name="Phase3 Test Material",
                code="P3-TEST", academic_year="2026",
                stage="Test", department="Test Dept",
            )
            mat_id = mat.id

        # 2. Create assessment
        with session_scope(factory) as session:
            ass = create_assessment(
                session, material_id=mat_id,
                title="Phase3 Test Assessment",
                assessment_type="Quiz", academic_year="2026",
                maximum_grade=Decimal("10"),
            )
            ass_id = ass.id

        # 3. Create questions
        with session_scope(factory) as session:
            create_question(session, ass_id, question_number=1, maximum_grade=Decimal("4"))
            create_question(session, ass_id, question_number=2, maximum_grade=Decimal("6"))
            questions = list_questions(session, ass_id)
            q_numbers = tuple(q.question_number for q in questions)

        # 4. Parse fixture
        preview = preview_html_import(
            load_fixture("sample_responses.html"), "sample_responses.html"
        )
        assert preview.parsed_import.statistics.total_rows == 5

        # 5. Reconcile
        reconciliation = reconcile_assessment(preview.parsed_import, q_numbers)
        assert reconciliation.exact_match is True

        # 6. Verify zero records in all persistence tables
        with session_scope(factory) as session:
            assert session.query(StudentIdentity).count() == 0
            assert session.query(AnonymousStudent).count() == 0
            assert session.query(ImportBatch).count() == 0
            assert session.query(Submission).count() == 0
            assert session.query(Response).count() == 0
            assert session.query(GradeRecord).count() == 0

        # 7. Verify material and assessment still exist (not deleted by preview)
        with session_scope(factory) as session:
            assert session.query(Material).count() == 1
            assert session.query(Assessment).count() == 1
            assert session.query(Question).count() == 2
