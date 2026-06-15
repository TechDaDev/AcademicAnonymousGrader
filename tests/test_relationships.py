from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.export_record import ExportRecord
from models.import_batch import ImportBatch
from models.material import Material
from models.question import Question
from models.student_identity import StudentIdentity


@pytest.fixture(scope="function")
def material_with_assessment(session: Session) -> dict[str, Any]:
    """Create a material with one assessment."""
    material = Material(name="Test Material")
    session.add(material)
    session.flush()

    assessment = Assessment(
        material_id=material.id, title="Test Assessment", maximum_grade=100.00
    )
    session.add(assessment)
    session.flush()
    return {"material": material, "assessment": assessment}


class TestMaterialToAssessment:
    """Material → Assessment relationship."""

    def test_material_has_assessments(self, session: Session, material_with_assessment: dict[str, Any]) -> None:
        material = material_with_assessment["material"]
        assert len(material.assessments) == 1
        assert material.assessments[0].title == "Test Assessment"


class TestAssessmentToQuestions:
    """Assessment → Question relationship."""

    def test_assessment_has_questions(self, session: Session, material_with_assessment: dict[str, Any]) -> None:
        assessment = material_with_assessment["assessment"]
        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=10.00)
        q2 = Question(assessment_id=assessment.id, question_number=2, maximum_grade=20.00)
        session.add_all([q1, q2])
        session.flush()

        assert len(assessment.questions) == 2


class TestAssessmentToImportBatch:
    """Assessment → ImportBatch relationship."""

    def test_assessment_has_import_batches(self, session: Session, material_with_assessment: dict[str, Any]) -> None:
        assessment = material_with_assessment["assessment"]
        batch = ImportBatch(
            assessment_id=assessment.id,
            source_filename="responses.html",
            source_format="html",
        )
        session.add(batch)
        session.flush()

        assert len(assessment.import_batches) == 1


class TestStudentIdentityToAnonymous:
    """StudentIdentity → AnonymousStudent relationship."""

    def test_identity_has_anonymous_student(self, session: Session) -> None:
        identity = StudentIdentity(encrypted_first_name="enc:Alice")
        session.add(identity)
        session.flush()

        anonymous = AnonymousStudent(
            student_identity_id=identity.id, anonymous_code="STU-TEST1234"
        )
        session.add(anonymous)
        session.flush()

        assert identity.anonymous_student is not None
        assert identity.anonymous_student.anonymous_code == "STU-TEST1234"


class TestAnonymousStudentToSubmission:
    """AnonymousStudent → Submission relationship."""

    def test_anonymous_student_has_submissions(self, session: Session, full_graph: dict[str, Any]) -> None:
        anonymous = full_graph["anonymous"]
        assert len(anonymous.submissions) == 1


class TestSubmissionToResponses:
    """Submission → Response relationship."""

    def test_submission_has_responses(self, session: Session, full_graph: dict[str, Any]) -> None:
        submission = full_graph["submission"]
        assert len(submission.responses) == 1


class TestSubmissionToGradeRecord:
    """Submission → GradeRecord relationship."""

    def test_submission_has_grade_records(self, session: Session, full_graph: dict[str, Any]) -> None:
        submission = full_graph["submission"]
        assert len(submission.grade_records) == 1
        assert submission.grade_records[0].grade == Decimal("7.50")
        assert submission.grade_records[0].grading_status == "graded"


class TestAssessmentToExportRecord:
    """Assessment → ExportRecord relationship."""

    def test_assessment_has_export_records(self, session: Session, material_with_assessment: dict[str, Any]) -> None:
        assessment = material_with_assessment["assessment"]
        export = ExportRecord(
            assessment_id=assessment.id,
            file_name="results.xlsx",
        )
        session.add(export)
        session.flush()

        assert len(assessment.export_records) == 1


class TestCascadeBehavior:
    """Verify cascade deletes are safe (no unsafe blanket deletes on identity)."""

    def test_delete_material_cascades_to_assessment(
        self, session: Session, material_with_assessment: dict[str, Any]
    ) -> None:
        material = material_with_assessment["material"]
        assessment_id = material_with_assessment["assessment"].id

        session.delete(material)
        session.flush()

        # Assessment should be deleted
        assert session.get(Assessment, assessment_id) is None

    def test_delete_assessment_does_not_delete_student_identity(
        self, session: Session, full_graph: dict[str, Any]
    ) -> None:
        assessment = full_graph["assessment"]
        identity_id = full_graph["identity"].id

        session.delete(assessment)
        session.flush()

        # Student identity should still exist
        assert session.get(StudentIdentity, identity_id) is not None
