"""ExportRecord model tests."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from models.assessment import Assessment
from models.export_record import ExportRecord
from models.material import Material


class TestExportRecord:
    def test_export_record_created(self, session: Session) -> None:
        material = Material(name="ER Test"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="ER", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        record = ExportRecord(
            assessment_id=assessment.id,
            export_format="xlsx",
            export_reference="EXP-TEST001",
            file_name="test.xlsx",
            file_hash="abc123",
            file_size=1024,
            row_count=5,
        )
        session.add(record); session.flush()
        assert record.id is not None
        assert record.export_reference == "EXP-TEST001"

    def test_multiple_exports_allowed(self, session: Session) -> None:
        material = Material(name="ER2"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="ER2", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        r1 = ExportRecord(assessment_id=assessment.id, file_name="a.xlsx")
        r2 = ExportRecord(assessment_id=assessment.id, file_name="b.xlsx")
        session.add_all([r1, r2]); session.flush()
        records = session.query(ExportRecord).filter(ExportRecord.assessment_id == assessment.id).all()
        assert len(records) == 2

    def test_no_identity_in_record(self, session: Session) -> None:
        material = Material(name="ER3"); session.add(material); session.flush()
        assessment = Assessment(material_id=material.id, title="ER3", maximum_grade=Decimal("100"))
        session.add(assessment); session.flush()
        record = ExportRecord(assessment_id=assessment.id, file_name="safe.xlsx")
        session.add(record); session.flush()
        assert not hasattr(record, "identity_data")
        assert not hasattr(record, "workbook_bytes")
