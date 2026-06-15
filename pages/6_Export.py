# Academic Anonymous Grader — Export Page
"""Phase 7: Finalization and Excel Export.

Workflow:
1. Select material
2. Select assessment
3. Display finalization readiness
4. Display blocking errors/warnings
5. Approve all submissions to satisfy readiness
6. Confirm and finalize
7. Download Excel workbook
8. Re-export as needed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.excel_export_service import generate_export_workbook
from services.exceptions import (
    AssessmentAlreadyFinalizedError,
    AssessmentNotReadyForFinalizationError,
    ExportWorkbookError,
    FinalizedAssessmentExportError,
)
from services.finalization_service import (
    FinalizationReadiness,
    finalize_assessment,
    get_finalization_readiness,
    get_finalized_assessment_summary,
)
from services.logging_service import get_logger
from services.material_service import list_materials
from services.review_service import list_reviewable_assessments
from ui.layout import configure_page, render_app_header, render_safe_error

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

logger = get_logger("export_page")

# ── Session state keys ────────────────────────────────────────────
_SEL_MATERIAL = "export_material_id"
_SEL_ASSESSMENT = "export_assessment_id"
_CONFIRMED = "export_confirmed"


def _reset_state() -> None:
    for key in (_SEL_ASSESSMENT, _CONFIRMED):
        st.session_state.pop(key, None)


def _render_readiness(readiness: FinalizationReadiness) -> None:
    """Render finalization readiness summary."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Submissions", readiness.total_submissions)
    col2.metric("Approved Submissions", readiness.approved_submissions)
    col3.metric("Ready", "✅ Yes" if readiness.is_ready else "❌ No")

    if readiness.blocking_errors:
        with st.expander(f"⚠️ Blocking Errors ({len(readiness.blocking_errors)})", expanded=True):
            for err in readiness.blocking_errors:
                st.error(f"[{err.code}] {err.message}")

    if readiness.warnings:
        with st.expander(f"⚠️ Warnings ({len(readiness.warnings)})"):
            for w in readiness.warnings:
                st.warning(f"[{w.code}] {w.message}")


def _render_finalized_summary(assessment_id: str, factory: sessionmaker) -> None:  # type: ignore[type-arg]
    """Render the finalized summary and export controls."""
    with session_scope(factory) as session:
        summary = get_finalized_assessment_summary(session, assessment_id)

    if summary is None:
        st.info("Assessment is not finalized yet.")
        return

    st.success(f"✅ **Assessment Finalized** — {summary.finalized_at}")

    cols = st.columns(4)
    cols[0].metric("Submissions", summary.total_submissions)
    cols[1].metric("Approved", summary.approved_submissions)
    cols[2].metric("Avg Grade", f"{summary.average_grade:.2f}")
    cols[3].metric("Total", f"{summary.final_grade_total:.2f} / {summary.maximum_total:.2f}")

    # Export section
    st.markdown("### 📥 Export Grades")
    st.caption("Generate an Excel workbook with restored identities.")

    settings = get_settings()

    if st.button("📥 Generate Workbook", type="primary", use_container_width=True):
        try:
            with session_scope(factory) as session:
                result = generate_export_workbook(session, assessment_id, settings)

            # Show export metadata
            st.success("✅ Workbook generated successfully!")
            meta_cols = st.columns(4)
            meta_cols[0].metric("Export Ref", result.export_reference)
            meta_cols[1].metric("Rows", result.row_count)
            meta_cols[2].metric("Size", f"{result.file_size / 1024:.1f} KB")
            meta_cols[3].metric("SHA-256", result.file_hash[:12] + "...")

            safe_filename = f"final_grades_{assessment_id[:8]}.xlsx"

            st.download_button(
                label="⬇️ Download Excel Workbook",
                data=result.workbook_bytes,
                file_name=safe_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Persist ExportRecord
            from datetime import UTC, datetime

            from models.export_record import ExportRecord

            with session_scope(factory) as session:
                record = ExportRecord(
                    assessment_id=assessment_id,
                    export_format="xlsx",
                    export_reference=result.export_reference,
                    file_name=safe_filename,
                    file_hash=result.file_hash,
                    file_size=result.file_size,
                    row_count=result.row_count,
                    exported_at=datetime.now(UTC),
                )
                session.add(record)

            st.caption("Export recorded. Re-export anytime — grades and finalization state remain unchanged.")

        except FinalizedAssessmentExportError as exc:
            render_safe_error(str(exc))
        except ExportWorkbookError as exc:
            render_safe_error(str(exc))
        except Exception as exc:
            logger.error("Export error: %s", type(exc).__name__)
            render_safe_error(f"Export failed: {exc}")

    # Show export history
    with session_scope(factory) as session:
        from models.export_record import ExportRecord as ExportRec
        records = (
            session.query(ExportRec)
            .filter(ExportRec.assessment_id == assessment_id)
            .order_by(ExportRec.created_at.desc())
            .all()
        )

    if records:
        st.markdown("### 📋 Export History")
        for rec in records:
            hash_preview = rec.file_hash[:12] + "..." if rec.file_hash else "N/A"
            size_display = f"{rec.file_size // 1024} KB" if rec.file_size else "N/A"
            st.caption(
                f"**{rec.export_reference}** — "
                f"{rec.exported_at} — "
                f"{rec.row_count} rows — "
                f"{size_display} — "
                f"SHA-256: {hash_preview}"
            )


def main() -> None:
    """Main entry point for the Export page."""
    configure_page("Export")
    render_app_header()
    st.subheader("📥 Finalization and Export")
    st.caption("Finalize assessments and generate Excel exports with restored identities.")

    settings = get_settings()
    engine = get_engine(settings.resolved_database_url())
    factory = create_session_factory(engine)

    # Step 1: Select material
    with session_scope(factory) as session:
        materials = list_materials(session, include_archived=False)
    if not materials:
        st.info("No active materials found. Create a material first.")
        return

    mat_options = {m.name: m for m in materials}
    sel_mat_name = st.selectbox(
        "1. Select Material",
        list(mat_options.keys()),
        key=_SEL_MATERIAL,
        on_change=_reset_state,
    )
    material = mat_options[sel_mat_name]

    # Step 2: Select assessment
    with session_scope(factory) as session:
        assessments = list_reviewable_assessments(session, material.id)

    if not assessments:
        st.info("No reviewable assessments found for this material.")
        return

    ass_options = {f"{a.title} ({a.status})": a for a in assessments}
    sel_ass_label = st.selectbox(
        "2. Select Assessment",
        list(ass_options.keys()),
        key=_SEL_ASSESSMENT,
    )
    assessment = ass_options[sel_ass_label]

    # Step 3: Check if already finalized
    with session_scope(factory) as session:
        from models.assessment import Assessment
        fresh = session.query(Assessment).filter(Assessment.id == assessment.id).first()

    if fresh and fresh.finalization_status == "finalized":
        _render_finalized_summary(assessment.id, factory)
        return

    # Step 4: Show readiness
    with session_scope(factory) as session:
        readiness = get_finalization_readiness(session, assessment.id)

    st.markdown("### 🔍 Finalization Readiness")
    _render_readiness(readiness)

    if readiness.is_ready:
        st.markdown("### 🚀 Finalize Assessment")
        st.caption("All submissions are approved and validated.")

        confirmed = st.checkbox(
            "I confirm that all grades and reviews are complete and that finalization will lock grading changes.",
            key=_CONFIRMED,
        )

        if confirmed:
            if st.button("🚀 Finalize Assessment", type="primary", use_container_width=True):
                try:
                    with session_scope(factory) as session:
                        result = finalize_assessment(session, assessment.id)
                    st.success(f"✅ Assessment finalized at {result.finalized_at}!")
                    st.rerun()
                except AssessmentAlreadyFinalizedError as exc:
                    render_safe_error(str(exc))
                except AssessmentNotReadyForFinalizationError as exc:
                    render_safe_error(str(exc))
                except Exception as exc:
                    logger.error("Finalization error: %s", type(exc).__name__)
                    render_safe_error(f"Finalization failed: {exc}")
    else:
        st.warning("⚠️ Assessment is not ready for finalization. Resolve all blocking errors above.")


if __name__ == "__main__":
    main()
