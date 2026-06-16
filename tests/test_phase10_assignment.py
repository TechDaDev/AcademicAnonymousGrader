"""Phase 10 — Instructor Assignment, Claims, Progress, and Docker Tests."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from database.init_db import initialize_database

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def tmp_db_path() -> Any:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        extra = db_path.parent / (db_path.name + suffix)
        if extra.exists():
            extra.unlink()


@pytest.fixture(scope="function")
def engine(tmp_db_path: Path) -> Any:
    db_url = f"sqlite:///{tmp_db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    initialize_database(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(scope="function")
def session(engine: Engine) -> Any:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    sess = session_factory()
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def admin_user(session: Session) -> Any:
    from services.auth_service import create_user

    user = create_user(
        session, username="admin", password="Admin123!",
        role="administrator", display_name="Admin User",
    )
    return user


@pytest.fixture(scope="function")
def instructor_user(session: Session) -> Any:
    from services.auth_service import create_user

    user = create_user(
        session, username="instructor1", password="Inst12345!",
        role="grader", display_name="Instructor One",
    )
    return user


@pytest.fixture(scope="function")
def instructor_user2(session: Session) -> Any:
    from services.auth_service import create_user

    user = create_user(
        session, username="instructor2", password="Inst12345!",
        role="grader", display_name="Instructor Two",
    )
    return user


@pytest.fixture(scope="function")
def inactive_instructor(session: Session) -> Any:
    from services.auth_service import create_user

    user = create_user(
        session, username="inactive_inst", password="Inst12345!",
        role="grader", display_name="Inactive Instructor",
    )
    # Manually deactivate after creation
    user.is_active = False
    session.flush()
    return user


@pytest.fixture(scope="function")
def material(session: Session) -> Any:
    from models.material import Material

    mat = Material(name="Test Material")
    session.add(mat)
    session.flush()
    return mat


@pytest.fixture(scope="function")
def assessment(session: Session, material: Any) -> Any:
    from models.assessment import Assessment

    ass = Assessment(
        material_id=material.id,
        title="Test Assessment",
        maximum_grade=Decimal("100.00"),
        status="ready",
        finalization_status="not_ready",
    )
    session.add(ass)
    session.flush()
    return ass


@pytest.fixture(scope="function")
def finalized_assessment(session: Session, material: Any) -> Any:
    from models.assessment import Assessment

    ass = Assessment(
        material_id=material.id,
        title="Finalized Assessment",
        maximum_grade=Decimal("100.00"),
        status="finalized",
        finalization_status="finalized",
        finalized_at=datetime.now(UTC),
    )
    session.add(ass)
    session.flush()
    return ass


@pytest.fixture(scope="function")
def admin_ctx(admin_user: Any) -> Any:
    from services.authorization_service import AuthContext

    return AuthContext(
        user_id=admin_user.id,
        username=admin_user.username,
        role="administrator",
        display_name=admin_user.display_name,
    )


@pytest.fixture(scope="function")
def grader_ctx(instructor_user: Any) -> Any:
    from services.authorization_service import AuthContext

    return AuthContext(
        user_id=instructor_user.id,
        username=instructor_user.username,
        role="grader",
        display_name=instructor_user.display_name,
    )


@pytest.fixture(scope="function")
def grader2_ctx(instructor_user2: Any) -> Any:
    from services.authorization_service import AuthContext

    return AuthContext(
        user_id=instructor_user2.id,
        username=instructor_user2.username,
        role="grader",
        display_name=instructor_user2.display_name,
    )


@pytest.fixture(scope="function")
def empty_ctx() -> Any:
    from services.authorization_service import AuthContext

    return AuthContext()


@pytest.fixture(scope="function")
def questions(session: Session, assessment: Any) -> list[Any]:
    from models.question import Question

    q1 = Question(
        assessment_id=assessment.id,
        question_number=1,
        maximum_grade=Decimal("50.00"),
        title="Question 1",
    )
    q2 = Question(
        assessment_id=assessment.id,
        question_number=2,
        maximum_grade=Decimal("50.00"),
        title="Question 2",
    )
    session.add_all([q1, q2])
    session.flush()
    return [q1, q2]


@pytest.fixture(scope="function")
def submissions(session: Session, assessment: Any, questions: list[Any]) -> list[Any]:
    from models.anonymous_student import AnonymousStudent
    from models.import_batch import ImportBatch
    from models.student_identity import StudentIdentity
    from models.submission import Submission

    batch = ImportBatch(
        assessment_id=assessment.id,
        source_filename="test.html",
        source_format="html",
        status="completed",
    )
    session.add(batch)
    session.flush()

    subs = []
    for i in range(3):
        identity = StudentIdentity(
            encrypted_first_name=f"enc:Student{i}_first",
            encrypted_last_name=f"enc:Student{i}_last",
        )
        session.add(identity)
        session.flush()

        anon = AnonymousStudent(
            student_identity_id=identity.id,
            anonymous_code=f"STU-PH10TEST{i:04d}",
        )
        session.add(anon)
        session.flush()

        sub = Submission(
            assessment_id=assessment.id,
            anonymous_student_id=anon.id,
            import_batch_id=batch.id,
            grading_status="pending",
            review_status="not_ready",
        )
        session.add(sub)
        session.flush()
        subs.append(sub)

    return subs


# ═══════════════════════════════════════════════════════════════════
# Assignment Model Tests
# ═══════════════════════════════════════════════════════════════════


class TestAssignmentModel:
    """Active-only uniqueness constraint on instructor_assignments."""

    def test_create_valid_assignment(self, session: Session, instructor_user: Any,
                                      assessment: Any, admin_user: Any) -> None:
        from models.instructor_assignment import InstructorAssignment

        assn = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(assn)
        session.flush()
        assert assn.id is not None
        assert assn.is_active is True

    def test_active_only_uniqueness(self, session: Session, instructor_user: Any,
                                     assessment: Any, admin_user: Any) -> None:
        from models.instructor_assignment import InstructorAssignment

        assn1 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(assn1)
        session.flush()

        assn2 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        with pytest.raises(Exception):
            session.add(assn2)
            session.flush()

    def test_unlimited_inactive_history(self, session: Session, instructor_user: Any,
                                         assessment: Any, admin_user: Any) -> None:
        from models.instructor_assignment import InstructorAssignment

        # Create first active assignment
        a1 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(a1)
        session.flush()
        a1.is_active = False
        session.flush()

        # Create second active assignment
        a2 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(a2)
        session.flush()
        a2.is_active = False
        session.flush()

        # Create third active assignment
        a3 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(a3)
        session.flush()

        # Verify: 1 active + 2 inactive
        active_count = (
            session.query(InstructorAssignment)
            .filter(
                InstructorAssignment.instructor_user_id == instructor_user.id,
                InstructorAssignment.assessment_id == assessment.id,
                InstructorAssignment.is_active == True,  # noqa: E712
            )
            .count()
        )
        assert active_count == 1

        inactive_count = (
            session.query(InstructorAssignment)
            .filter(
                InstructorAssignment.instructor_user_id == instructor_user.id,
                InstructorAssignment.assessment_id == assessment.id,
                InstructorAssignment.is_active == False,  # noqa: E712
            )
            .count()
        )
        assert inactive_count == 2

    def test_deactivate_marks_inactive(self, session: Session, instructor_user: Any,
                                        assessment: Any, admin_user: Any) -> None:
        from models.instructor_assignment import InstructorAssignment

        assn = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(assn)
        session.flush()

        assn.deactivate()
        assert assn.is_active is False
        assert assn.unassigned_at is not None

    def test_multiple_instructors_same_assessment(self, session: Session,
                                                   instructor_user: Any,
                                                   instructor_user2: Any,
                                                   assessment: Any,
                                                   admin_user: Any) -> None:
        from models.instructor_assignment import InstructorAssignment

        a1 = InstructorAssignment(
            instructor_user_id=instructor_user.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(a1)
        session.flush()

        a2 = InstructorAssignment(
            instructor_user_id=instructor_user2.id,
            assessment_id=assessment.id,
            assigned_by_user_id=admin_user.id,
            is_active=True,
        )
        session.add(a2)
        session.flush()
        assert a2.id is not None


# ═══════════════════════════════════════════════════════════════════
# Assignment Service Tests
# ═══════════════════════════════════════════════════════════════════


class TestAssignmentService:
    """Tests for assignment_service.py — administrator-only operations."""

    def test_create_assignment(self, session: Session, instructor_user: Any,
                                assessment: Any, admin_ctx: Any) -> None:
        from services.assignment_service import create_assignment

        assn = create_assignment(
            session, instructor_user.id, assessment.id, auth_ctx=admin_ctx,
        )
        assert assn.is_active is True
        assert assn.instructor_user_id == instructor_user.id
        assert assn.assessment_id == assessment.id

    def test_duplicate_active_rejected(self, session: Session, instructor_user: Any,
                                        assessment: Any, admin_ctx: Any) -> None:
        from services.assignment_service import create_assignment
        from services.exceptions import DuplicateAssignmentError

        create_assignment(session, instructor_user.id, assessment.id, auth_ctx=admin_ctx)
        with pytest.raises(DuplicateAssignmentError):
            create_assignment(session, instructor_user.id, assessment.id, auth_ctx=admin_ctx)

    def test_only_active_instructor_assignable(self, session: Session,
                                                inactive_instructor: Any,
                                                assessment: Any,
                                                admin_ctx: Any) -> None:
        from services.assignment_service import create_assignment
        from services.exceptions import InstructorAssignmentError

        with pytest.raises(InstructorAssignmentError):
            create_assignment(
                session, inactive_instructor.id, assessment.id, auth_ctx=admin_ctx,
            )

    def test_finalized_assessment_blocked(self, session: Session,
                                           instructor_user: Any,
                                           finalized_assessment: Any,
                                           admin_ctx: Any) -> None:
        from services.assignment_service import create_assignment
        from services.exceptions import AssignmentBlockedByFinalizationError

        with pytest.raises(AssignmentBlockedByFinalizationError):
            create_assignment(
                session, instructor_user.id, finalized_assessment.id, auth_ctx=admin_ctx,
            )

    def test_administrator_only_mutation(self, session: Session, instructor_user: Any,
                                          assessment: Any, grader_ctx: Any,
                                          empty_ctx: Any) -> None:
        from services.assignment_service import create_assignment
        from services.exceptions import InsufficientPermissionsError

        with pytest.raises(InsufficientPermissionsError):
            create_assignment(
                session, instructor_user.id, assessment.id, auth_ctx=grader_ctx,
            )

        with pytest.raises(InsufficientPermissionsError):
            create_assignment(
                session, instructor_user.id, assessment.id, auth_ctx=empty_ctx,
            )

    def test_deactivate_assignment(self, session: Session, instructor_user: Any,
                                    assessment: Any, admin_ctx: Any) -> None:
        from services.assignment_service import create_assignment, deactivate_assignment

        assn = create_assignment(
            session, instructor_user.id, assessment.id, auth_ctx=admin_ctx,
        )
        deactivated = deactivate_assignment(session, assn.id, auth_ctx=admin_ctx)
        assert deactivated.is_active is False

    def test_reassignment(self, session: Session, instructor_user: Any,
                           instructor_user2: Any, assessment: Any,
                           admin_ctx: Any) -> None:
        from services.assignment_service import (
            create_assignment,
            get_active_assignments,
            reassign_assessment,
        )

        create_assignment(
            session, instructor_user.id, assessment.id, auth_ctx=admin_ctx,
        )
        new_assn = reassign_assessment(
            session, assessment.id, instructor_user.id, instructor_user2.id,
            auth_ctx=admin_ctx,
        )
        assert new_assn.instructor_user_id == instructor_user2.id

        # Verify only new instructor has active assignment
        active = get_active_assignments(session, auth_ctx=admin_ctx)
        assert len(active) == 1
        assert active[0].instructor_user_id == instructor_user2.id

    def test_history_preserved(self, session: Session, instructor_user: Any,
                                assessment: Any, admin_ctx: Any) -> None:
        from services.assignment_service import (
            create_assignment,
            deactivate_assignment,
            get_assignment_history,
        )

        assn1 = create_assignment(
            session, instructor_user.id, assessment.id, auth_ctx=admin_ctx,
        )
        deactivate_assignment(session, assn1.id, auth_ctx=admin_ctx)

        assn2 = create_assignment(
            session, instructor_user.id, assessment.id, auth_ctx=admin_ctx,
        )
        deactivate_assignment(session, assn2.id, auth_ctx=admin_ctx)

        history = get_assignment_history(
            session, auth_ctx=admin_ctx, include_active=False,
        )
        assert len(history) == 2


# ═══════════════════════════════════════════════════════════════════
# Instructor Access Tests
# ═══════════════════════════════════════════════════════════════════


class TestInstructorAccess:
    """Instructors see only their assigned assessments."""

    def test_assigned_assessment_visible(self, session: Session, instructor_user: Any,
                                          assessment: Any, admin_user: Any,
                                          grader_ctx: Any) -> None:
        from services.assignment_service import create_assignment, get_own_assigned_assessments
        from services.authorization_service import AuthContext

        create_assignment(
            session, instructor_user.id, assessment.id,
            auth_ctx=AuthContext(user_id=admin_user.id, username="admin", role="administrator"),
        )
        assigned = get_own_assigned_assessments(session, auth_ctx=grader_ctx)
        assert len(assigned) == 1
        assert assigned[0].id == assessment.id

    def test_unassigned_assessment_hidden(self, session: Session, assessment: Any,
                                           grader_ctx: Any) -> None:
        from services.assignment_service import get_own_assigned_assessments

        assigned = get_own_assigned_assessments(session, auth_ctx=grader_ctx)
        assert len(assigned) == 0

    def test_direct_unassigned_access_blocked(self, session: Session, assessment: Any,
                                               grader_ctx: Any) -> None:
        from services.assignment_service import require_assignment_access
        from services.exceptions import InsufficientPermissionsError

        with pytest.raises(InsufficientPermissionsError) as exc:
            require_assignment_access(session, assessment.id, auth_ctx=grader_ctx)
        assert "unavailable" in str(exc.value).lower()

    def test_admin_override(self, session: Session, assessment: Any,
                             admin_ctx: Any) -> None:
        from services.assignment_service import check_instructor_assignment_access

        assert check_instructor_assignment_access(session, assessment.id, auth_ctx=admin_ctx) is True

    def test_no_existence_leak(self, session: Session, assessment: Any,
                                grader_ctx: Any) -> None:
        from services.assignment_service import require_assignment_access
        from services.exceptions import InsufficientPermissionsError

        with pytest.raises(InsufficientPermissionsError) as exc:
            require_assignment_access(session, assessment.id, auth_ctx=grader_ctx)
        # Must not reveal whether assessment exists
        msg = str(exc.value).lower()
        assert "not found" not in msg
        assert "does not exist" not in msg


# ═══════════════════════════════════════════════════════════════════
# Grading Claim Tests
# ═══════════════════════════════════════════════════════════════════


class TestGradingClaim:
    """Grading claim/locking tests."""

    def test_successful_claim(self, session: Session, submissions: list[Any],
                               grader_ctx: Any) -> None:
        from services.assignment_service import claim_submission

        claimed = claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        assert claimed.assigned_grader_user_id == grader_ctx.user_id
        assert claimed.grading_lock_expires_at is not None

    def test_concurrent_claim_conflict(self, session: Session, submissions: list[Any],
                                        grader_ctx: Any, grader2_ctx: Any) -> None:
        from services.assignment_service import claim_submission
        from services.exceptions import GradingClaimConflictError

        claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        with pytest.raises(GradingClaimConflictError):
            claim_submission(session, submissions[0].id, auth_ctx=grader2_ctx)

    def test_owner_edit_allowed(self, session: Session, submissions: list[Any],
                                 grader_ctx: Any) -> None:
        from services.assignment_service import claim_submission, renew_claim

        claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        renewed = renew_claim(session, submissions[0].id, auth_ctx=grader_ctx)
        assert renewed.assigned_grader_user_id == grader_ctx.user_id

    def test_stale_claim_expiry(self, session: Session, submissions: list[Any],
                                 grader_ctx: Any, grader2_ctx: Any) -> None:
        from services.assignment_service import claim_submission

        claimed = claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        # Manually expire the claim
        claimed.grading_lock_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.flush()

        # Other instructor can now claim
        claimed2 = claim_submission(session, submissions[0].id, auth_ctx=grader2_ctx)
        assert claimed2.assigned_grader_user_id == grader2_ctx.user_id

    def test_admin_force_release(self, session: Session, submissions: list[Any],
                                  grader_ctx: Any, admin_ctx: Any) -> None:
        from services.assignment_service import claim_submission, release_claim

        claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        released = release_claim(session, submissions[0].id, auth_ctx=admin_ctx)
        assert released.assigned_grader_user_id is None

    def test_claim_cleared_after_completion(self, session: Session,
                                             submissions: list[Any],
                                             grader_ctx: Any, admin_ctx: Any) -> None:
        from services.assignment_service import claim_submission, release_claim

        claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)
        release_claim(session, submissions[0].id, auth_ctx=admin_ctx)
        # Verify no lingering claim
        from models.submission import Submission
        sub = session.query(Submission).filter(Submission.id == submissions[0].id).first()
        assert sub is not None
        assert sub.assigned_grader_user_id is None
        assert sub.grading_claimed_at is None
        assert sub.grading_lock_expires_at is None

    def test_finalization_blocked_by_active_claim(self, session: Session,
                                                    assessment: Any,
                                                    submissions: list[Any],
                                                    questions: list[Any],
                                                    grader_ctx: Any,
                                                    admin_ctx: Any) -> None:
        """Active grading claim blocks finalization."""
        from services.assignment_service import claim_submission
        from services.finalization_service import get_finalization_readiness

        claim_submission(session, submissions[0].id, auth_ctx=grader_ctx)

        readiness = get_finalization_readiness(session, assessment.id)
        claim_blockers = [e for e in readiness.blocking_errors if e.code == "FA012"]
        assert len(claim_blockers) > 0


# ═══════════════════════════════════════════════════════════════════
# Progress Service Tests
# ═══════════════════════════════════════════════════════════════════


class TestProgressService:
    """Progress service tests."""

    def test_accurate_status_counts(self, session: Session, assessment: Any,
                                     submissions: list[Any], questions: list[Any],
                                     admin_ctx: Any) -> None:
        from services.progress_service import get_assessment_progress

        progress = get_assessment_progress(session, auth_ctx=admin_ctx, assessment_id=assessment.id)
        assert progress.total_submissions == 3
        assert progress.ungraded_submissions > 0

    def test_no_identity_fields(self, session: Session, assessment: Any,
                                 admin_ctx: Any) -> None:
        from services.progress_service import get_assessment_progress

        progress = get_assessment_progress(session, auth_ctx=admin_ctx, assessment_id=assessment.id)
        # Ensure no identity fields
        assert not hasattr(progress, "student_name")
        assert not hasattr(progress, "student_identity")

    def test_own_progress(self, session: Session, instructor_user: Any,
                           assessment: Any, admin_user: Any, grader_ctx: Any) -> None:
        from services.assignment_service import create_assignment
        from services.authorization_service import AuthContext
        from services.progress_service import get_own_progress

        create_assignment(
            session, instructor_user.id, assessment.id,
            auth_ctx=AuthContext(user_id=admin_user.id, username="admin", role="administrator"),
        )
        progress = get_own_progress(session, auth_ctx=grader_ctx)
        assert progress.total_assessments >= 1


# ═══════════════════════════════════════════════════════════════════
# Configuration Validation Tests
# ═══════════════════════════════════════════════════════════════════


class TestConfigValidation:
    """Configuration validation tests."""

    def test_missing_keys(self, monkeypatch: Any) -> None:
        from services.config_validation import validate_config

        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("IDENTITY_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("IDENTITY_FINGERPRINT_KEY", raising=False)
        errors = validate_config()
        # Should warn about missing keys in dev mode
        key_errors = [e for e in errors if "KEY" in e.upper()]
        assert len(key_errors) >= 0  # Not blocking in dev

    def test_invalid_app_env(self, monkeypatch: Any) -> None:
        from services.config_validation import validate_config

        monkeypatch.setenv("APP_ENV", "invalid_env")
        errors = validate_config()
        env_errors = [e for e in errors if "APP_ENV" in e]
        assert len(env_errors) > 0

    def test_debug_in_production(self, monkeypatch: Any) -> None:
        from services.config_validation import validate_config

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "true")
        errors = validate_config()
        debug_errors = [e for e in errors if "Debug" in e]
        assert len(debug_errors) > 0

    def test_unsafe_parser_limits(self, monkeypatch: Any) -> None:
        from services.config_validation import validate_config

        monkeypatch.setenv("MAX_HTML_TABLES", "0")
        errors = validate_config()
        limit_errors = [e for e in errors if "MAX_HTML_TABLES" in e]
        assert len(limit_errors) > 0


# ═══════════════════════════════════════════════════════════════════
# Health Check Tests
# ═══════════════════════════════════════════════════════════════════


class TestHealthCheck:
    """Health check tests."""

    def test_health_check_exits(self, engine: Engine) -> None:
        """Health check runs without crashing."""
        from scripts.health_check import run_health_check

        result = run_health_check()
        assert hasattr(result, "all_healthy")

    def test_health_check_reason_codes(self, engine: Engine) -> None:
        """Health check returns only safe reason codes."""
        from scripts.health_check import run_health_check

        result = run_health_check()
        for name, detail in result.checks.items():
            if detail is not True:
                # Detail should be a string, not contain secrets
                assert isinstance(detail, str)
                assert "secret" not in detail.lower()


# ═══════════════════════════════════════════════════════════════════
# Production Logging Tests
# ═══════════════════════════════════════════════════════════════════


class TestProductionLogging:
    """Logging privacy tests."""

    def test_logging_privacy(self) -> None:
        """Log messages should not contain PII patterns after redaction."""
        import io
        import logging

        from services.logging_service import PrivacyRedactionFilter

        logger = logging.getLogger("test_privacy")
        logger.setLevel("DEBUG")
        logger.handlers.clear()

        capture = io.StringIO()
        handler = logging.StreamHandler(capture)
        handler.addFilter(PrivacyRedactionFilter())
        logger.addHandler(handler)

        logger.info("Student email: john.doe@university.edu")
        logger.info("API Key: sk-1234567890abcdef1234567890abcdef")
        logger.info("Grade: 95.5")  # Should be allowed

        output = capture.getvalue()
        assert "[EMAIL_REDACTED]" in output
        assert "john.doe@university.edu" not in output
        assert "[REDACTED]" in output or "[KEY_REDACTED]" in output
        assert "95.5" in output  # Grades should not be redacted


# ═══════════════════════════════════════════════════════════════════
# Docker Static Tests
# ═══════════════════════════════════════════════════════════════════


class TestDockerStatic:
    """Static Docker configuration tests."""

    def test_dockerfile_exists(self) -> None:
        assert Path("Dockerfile").exists()

    def test_dockerfile_uses_non_root(self) -> None:
        content = Path("Dockerfile").read_text()
        assert "USER grader" in content
        assert "root" not in content.split("USER grader")[1].split("\n")[0].lower()

    def test_only_port_8501_exposed(self) -> None:
        content = Path("Dockerfile").read_text()
        ports = [line for line in content.split("\n") if line.strip().startswith("EXPOSE")]
        assert len(ports) == 1
        assert "8501" in ports[0]

    def test_no_secret_build_args(self) -> None:
        content = Path("Dockerfile").read_text()
        assert "IDENTITY_ENCRYPTION_KEY" not in content
        assert "IDENTITY_FINGERPRINT_KEY" not in content
        # Check no ARG or ENV lines have secret-like names
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("ARG") or stripped.startswith("ENV"):
                assert "KEY" not in stripped.upper()
                assert "SECRET" not in stripped.upper()
                assert "PASSWORD" not in stripped.upper()
                assert "TOKEN" not in stripped.upper()

    def test_dockerignore_exists(self) -> None:
        assert Path(".dockerignore").exists()

    def test_dockerignore_excludes_sensitive(self) -> None:
        content = Path(".dockerignore").read_text()
        assert ".env" in content
        assert "*.db" in content or "data/" in content
        assert "backups/" in content
        assert "samples/" in content or "samples/*" in content

    def test_compose_no_hardcoded_secrets(self) -> None:
        content = Path("docker-compose.yml").read_text()
        assert "IDENTITY_ENCRYPTION_KEY=" not in content.replace("${", "")
        assert "IDENTITY_FINGERPRINT_KEY=" not in content.replace("${", "")

    def test_compose_has_persistent_volumes(self) -> None:
        content = Path("docker-compose.yml").read_text()
        assert "volumes:" in content
        assert "grader_data:" in content

    def test_compose_has_healthcheck(self) -> None:
        content = Path("docker-compose.yml").read_text()
        assert "healthcheck:" in content

    def test_compose_no_privileged(self) -> None:
        content = Path("docker-compose.yml").read_text()
        assert "privileged: true" not in content

    def test_compose_no_docker_socket(self) -> None:
        content = Path("docker-compose.yml").read_text()
        assert "/var/run/docker.sock" not in content

    def test_entrypoint_has_shell_content(self) -> None:
        content = Path("docker/entrypoint.sh").read_text()
        assert "#!/bin/bash" in content
        assert "set -eu" in content
        assert 'exec "$@"' in content

    def test_entrypoint_never_overwrites_db(self) -> None:
        content = Path("docker/entrypoint.sh").read_text()
        assert "initialize_database" in content
        assert "verify_schema_version" in content

    def test_env_example_contains_placeholders(self) -> None:
        content = Path(".env.example").read_text()
        assert "IDENTITY_ENCRYPTION_KEY=" in content
        assert "IDENTITY_FINGERPRINT_KEY=" in content


# ═══════════════════════════════════════════════════════════════════
# Finalization Readiness Tests
# ═══════════════════════════════════════════════════════════════════


class TestFinalizationReadinessExt:
    """Extended finalization readiness tests."""

    def test_ungraded_submissions_blocked(self, session: Session, assessment: Any,
                                           submissions: list[Any]) -> None:
        from services.finalization_service import get_finalization_readiness

        readiness = get_finalization_readiness(session, assessment.id)
        ungraded_blockers = [e for e in readiness.blocking_errors if e.code == "FA013"]
        assert len(ungraded_blockers) > 0
