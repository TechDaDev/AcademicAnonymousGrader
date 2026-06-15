# Academic Anonymous Grader — Test Configuration
"""pytest fixtures for all tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from database.init_db import initialize_database


@pytest.fixture(scope="function")
def tmp_db_path() -> Generator[Path, None, None]:
    """Create a temporary SQLite database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()
    # Also clean up WAL and SHM files
    for suffix in ("-wal", "-shm"):
        extra = db_path.parent / (db_path.name + suffix)
        if extra.exists():
            extra.unlink()


@pytest.fixture(scope="function")
def engine(tmp_db_path: Path) -> Generator[Engine, None, None]:
    """Create a temporary SQLite engine with foreign keys enabled."""
    db_url = f"sqlite:///{tmp_db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:  # noqa: ANN401
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    initialize_database(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="function")
def session(engine: Engine) -> Generator[Session, None, None]:
    """Provide a database session within a transaction that rolls back."""
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def full_graph(session: Session) -> dict[str, Any]:
    """Create a complete object graph for relationship testing."""
    from models.anonymous_student import AnonymousStudent
    from models.assessment import Assessment
    from models.grade_record import GradeRecord
    from models.import_batch import ImportBatch
    from models.material import Material
    from models.question import Question
    from models.response import Response
    from models.student_identity import StudentIdentity
    from models.submission import Submission

    material = Material(name="Test Material")
    session.add(material)
    session.flush()

    assessment = Assessment(
        material_id=material.id,
        title="Test Assessment",
        maximum_grade=100.00,
    )
    session.add(assessment)
    session.flush()

    question1 = Question(
        assessment_id=assessment.id,
        question_number=1,
        maximum_grade=10.00,
        title="Question 1",
    )
    question2 = Question(
        assessment_id=assessment.id,
        question_number=2,
        maximum_grade=20.00,
        title="Question 2",
    )
    session.add_all([question1, question2])
    session.flush()

    identity = StudentIdentity(
        encrypted_first_name="enc:Alice",
        encrypted_last_name="enc:Smith",
    )
    session.add(identity)
    session.flush()

    anonymous = AnonymousStudent(
        student_identity_id=identity.id,
        anonymous_code="STU-TEST9999",
    )
    session.add(anonymous)
    session.flush()

    batch = ImportBatch(
        assessment_id=assessment.id,
        source_filename="test.html",
        source_format="html",
        status="completed",
    )
    session.add(batch)
    session.flush()

    submission = Submission(
        assessment_id=assessment.id,
        anonymous_student_id=anonymous.id,
        import_batch_id=batch.id,
    )
    session.add(submission)
    session.flush()

    response1 = Response(
        submission_id=submission.id,
        question_id=question1.id,
        response_text="Answer to question 1",
    )
    session.add(response1)
    session.flush()

    grade1 = GradeRecord(
        submission_id=submission.id,
        question_id=question1.id,
        grade=Decimal("7.50"),
        grading_status="graded",
    )
    session.add(grade1)
    session.flush()

    return {
        "material": material,
        "assessment": assessment,
        "question1": question1,
        "question2": question2,
        "identity": identity,
        "anonymous": anonymous,
        "batch": batch,
        "submission": submission,
        "response1": response1,
        "grade1": grade1,
    }
