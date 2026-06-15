from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.anonymous_student import AnonymousStudent
from models.assessment import Assessment
from models.grade_record import GradeRecord
from models.material import Material
from models.question import Question
from models.response import Response
from models.student_identity import StudentIdentity


class TestUUIDPrimaryKeys:
    """Verify UUID primary keys are generated."""

    def test_material_uuid(self, session: Session) -> None:
        material = Material(name="Test Course")
        session.add(material)
        session.flush()
        assert material.id is not None
        assert isinstance(material.id, str)
        # Valid UUID check
        uuid.UUID(material.id)

    def test_student_identity_uuid(self, session: Session) -> None:
        identity = StudentIdentity(encrypted_first_name="enc:John")
        session.add(identity)
        session.flush()
        assert identity.id is not None
        uuid.UUID(identity.id)


class TestMaterialModel:
    """Material CRUD and relationships."""

    def test_create_and_retrieve_material(self, session: Session) -> None:
        material = Material(name="Object-Oriented Programming")
        session.add(material)
        session.flush()

        retrieved = session.get(Material, material.id)
        assert retrieved is not None
        assert retrieved.name == "Object-Oriented Programming"


class TestAssessmentModel:
    """Assessment relationships."""

    def test_assessment_belongs_to_material(self, session: Session) -> None:
        material = Material(name="DBOAIC1101")
        session.add(material)
        session.flush()

        assessment = Assessment(
            material_id=material.id,
            title="Midterm Exam",
            maximum_grade=100.00,
        )
        session.add(assessment)
        session.flush()

        assert assessment.material_id == material.id
        assert assessment.material.name == "DBOAIC1101"


class TestQuestionModel:
    """Question relationships and constraints."""

    def test_question_belongs_to_assessment(self, session: Session) -> None:
        material = Material(name="Course")
        session.add(material)
        session.flush()

        assessment = Assessment(
            material_id=material.id, title="Exam", maximum_grade=50.00
        )
        session.add(assessment)
        session.flush()

        question = Question(
            assessment_id=assessment.id,
            question_number=1,
            maximum_grade=10.00,
        )
        session.add(question)
        session.flush()

        assert question.assessment_id == assessment.id

    def test_question_number_unique_per_assessment(self, session: Session) -> None:
        material = Material(name="Course")
        session.add(material)
        session.flush()

        assessment = Assessment(
            material_id=material.id, title="Exam", maximum_grade=50.00
        )
        session.add(assessment)
        session.flush()

        q1 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=10.00)
        q2 = Question(assessment_id=assessment.id, question_number=1, maximum_grade=5.00)
        session.add_all([q1, q2])

        with pytest.raises(IntegrityError):
            session.flush()


class TestStudentIdentityModel:
    """StudentIdentity constraints and safety."""

    def test_student_identity_can_exist_without_email(self, session: Session) -> None:
        identity = StudentIdentity(encrypted_first_name="enc:John", encrypted_last_name="enc:Doe")
        session.add(identity)
        session.flush()
        assert identity.encrypted_email is None

    def test_duplicate_email_values_allowed(self, session: Session) -> None:
        i1 = StudentIdentity(
            encrypted_first_name="enc:John",
            encrypted_email="enc:john@example.com",
            email_fingerprint="fp:john@example.com",
        )
        i2 = StudentIdentity(
            encrypted_first_name="enc:Jane",
            encrypted_email="enc:john@example.com",
            email_fingerprint="fp:john@example.com",
        )
        session.add_all([i1, i2])
        session.flush()  # Should not raise

    def test_repr_does_not_expose_pii(self, session: Session) -> None:
        identity = StudentIdentity(
            encrypted_first_name="enc:John", encrypted_last_name="enc:Doe",
            encrypted_email="enc:john@example.com",
        )
        session.add(identity)
        session.flush()
        representation = repr(identity)
        assert "John" not in representation
        assert "Doe" not in representation
        assert "john@example.com" not in representation


class TestAnonymousStudentModel:
    """AnonymousStudent constraints."""

    def test_anonymous_code_is_unique(self, session: Session) -> None:
        identity1 = StudentIdentity(encrypted_first_name="enc:Alice")
        identity2 = StudentIdentity(encrypted_first_name="enc:Bob")
        session.add_all([identity1, identity2])
        session.flush()

        a1 = AnonymousStudent(
            student_identity_id=identity1.id, anonymous_code="STU-ABCD1234"
        )
        a2 = AnonymousStudent(
            student_identity_id=identity2.id, anonymous_code="STU-ABCD1234"
        )
        session.add_all([a1, a2])

        with pytest.raises(IntegrityError):
            session.flush()


class TestResponseModel:
    """Response constraints."""

    def test_response_unique_per_submission_and_question(self, session: Session, full_graph: dict[str, Any]) -> None:
        r1 = Response(
            submission_id=full_graph["submission"].id,
            question_id=full_graph["question1"].id,
            response_text="Answer 1",
        )
        r2 = Response(
            submission_id=full_graph["submission"].id,
            question_id=full_graph["question1"].id,
            response_text="Answer 2",
        )
        session.add_all([r1, r2])

        with pytest.raises(IntegrityError):
            session.flush()

    def test_response_text_not_in_repr(self, session: Session, full_graph: dict[str, Any]) -> None:
        # Use question2 (different from question1 used in full_graph fixture)
        response = Response(
            submission_id=full_graph["submission"].id,
            question_id=full_graph["question2"].id,
            response_text="Secret answer",
        )
        session.add(response)
        session.flush()
        assert "Secret answer" not in repr(response)


class TestGradeRecordModel:
    """GradeRecord constraints."""

    def test_grade_record_unique_per_submission_question(self, session: Session, full_graph: dict[str, Any]) -> None:
        g1 = GradeRecord(
            submission_id=full_graph["submission"].id,
            question_id=full_graph["question1"].id,
            grade=Decimal("8.00"),
        )
        g2 = GradeRecord(
            submission_id=full_graph["submission"].id,
            question_id=full_graph["question1"].id,
            grade=Decimal("9.00"),
        )
        session.add_all([g1, g2])

        with pytest.raises(IntegrityError):
            session.flush()


class TestNumericFields:
    """Verify decimal values are preserved."""

    def test_numeric_fields_preserve_decimal_values(self, session: Session) -> None:
        material = Material(name="Test")
        session.add(material)
        session.flush()

        assessment = Assessment(
            material_id=material.id, title="Test", maximum_grade=Decimal("99.99")
        )
        session.add(assessment)
        session.flush()

        assert isinstance(assessment.maximum_grade, Decimal)
        assert assessment.maximum_grade == Decimal("99.99")

    def test_exact_decimal_value_is_preserved(self, session: Session) -> None:
        material = Material(name="DecimalTest")
        session.add(material)
        session.flush()

        assessment = Assessment(
            material_id=material.id, title="DecimalAssessment", maximum_grade=Decimal("7.25")
        )
        session.add(assessment)
        session.flush()

        assert assessment.maximum_grade == Decimal("7.25")
        assert isinstance(assessment.maximum_grade, Decimal)
