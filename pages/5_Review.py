# Academic Anonymous Grader — Review Page
"""Phase 6: Review and Validation — review graded submissions and approve."""

from __future__ import annotations

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.logging_service import get_logger
from services.material_service import list_materials
from services.review_service import (
    AssessmentValidationResult,
    ReviewProgress,
    ReviewSubmissionSummary,
    ReviewSubmissionView,
    approve_submission_review,
    calculate_review_progress,
    get_review_submission,
    list_review_submissions,
    mark_submission_needs_correction,
    return_submission_to_grading,
    validate_assessment_review,
)
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import require_authentication, require_page_access_safe

logger = get_logger("review_page")

# ── Session state keys ────────────────────────────────────────────
_SEL_MATERIAL = "review_material_id"
_SEL_ASSESSMENT = "review_assessment_id"
_SEL_SUBMISSION = "review_submission_id"
_FILTER = "review_filter"
_NOTE_INPUT = "review_note_input"


def _reset_assessment_state() -> None:
    for key in [_SEL_SUBMISSION, _NOTE_INPUT]:
        if key in st.session_state:
            del st.session_state[key]


def _render_progress(progress: ReviewProgress) -> None:
    st.markdown("### Review Progress")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total", progress.total_submissions)
    c2.metric("Not Ready", progress.not_ready)
    c3.metric("Ready for Review", progress.ready_for_review)
    c4.metric("Needs Correction", progress.needs_correction)
    c5.metric("Approved", progress.approved)
    c6.metric("Completion", f"{progress.completion_percentage}%")


def _render_assessment_validation(result: AssessmentValidationResult) -> None:
    st.markdown("### Assessment Validation")
    if result.is_ready:
        st.success("✅ All checks passed — assessment is ready.")
    else:
        st.warning("⚠️ Assessment has unresolved issues.")

    for err in result.blocking_errors:
        st.error(f"[{err.code}] {err.message}")
    for warn in result.warnings:
        st.warning(f"[{warn.code}] {warn.message}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total submissions", result.total_submissions)
    c2.metric("Graded", result.graded_submissions)
    c3.metric("Approved", result.approved_submissions)


def _render_submission_list(
    submissions: list[ReviewSubmissionSummary],
    current_sub: str | None,
) -> str | None:
    st.markdown("### Submissions")
    selected_filter = st.radio(
        "Filter",
        [
            "All",
            "Not Ready",
            "Ready for Review",
            "Needs Correction",
            "Approved",
            "Has Errors",
            "Has Warnings",
        ],
        key=_FILTER,
        horizontal=True,
    )

    filter_map = {
        "All": None,
        "Not Ready": "not_ready",
        "Ready for Review": "ready_for_review",
        "Needs Correction": "needs_correction",
        "Approved": "approved",
    }
    if selected_filter == "Has Errors":
        filtered = [s for s in submissions if s.validation_error_count > 0]
    elif selected_filter == "Has Warnings":
        filtered = [s for s in submissions if s.validation_warning_count > 0]
    else:
        flt = filter_map[selected_filter]
        filtered = [s for s in submissions if flt is None or s.review_status == flt]

    for s in filtered:
        status_icon = {
            "not_ready": "⬜",
            "ready_for_review": "📋",
            "needs_correction": "⚠️",
            "approved": "✅",
        }.get(s.review_status, "⬜")

        err_badge = f" ⚠️{s.validation_error_count}e" if s.validation_error_count > 0 else ""
        label = (
            f"{status_icon} {s.anonymous_code} — "
            f"{s.total_grade}/{s.maximum_grade}"
            f" | {s.review_status}{err_badge}"
        )
        sub_id: str = s.submission_id
        btn_key = f"rev_btn_{sub_id}"
        if st.button(label, key=btn_key, use_container_width=True):
            return sub_id

    return None


def _render_review_panel(view: ReviewSubmissionView) -> tuple[bool, bool, bool, str]:
    st.markdown(f"### Review: {view.anonymous_code}")
    st.caption(f"Assessment: {view.assessment_title}")
    st.caption(f"Total: {view.total_grade} / {view.maximum_grade}  |  Status: {view.review_status}")

    if view.validation_errors:
        st.error(f"**{len(view.validation_errors)} blocking error(s):**")
        for err in view.validation_errors:
            st.error(f"[{err.code}] {err.message}")
    if view.validation_warnings:
        st.warning(f"**{len(view.validation_warnings)} warning(s):**")
        for w in view.validation_warnings:
            st.warning(f"[{w.code}] {w.message}")

    for q in view.questions:
        st.markdown(f"#### Question {q.question_number}: {q.question_title or ''}")
        st.caption(f"Max: {q.maximum_grade}  |  Grade: {q.grade or '(ungraded)'}  |  Status: {q.grading_status}")

        if q.is_blank:
            st.caption("*(blank response)*")
        elif q.response_text:
            st.code(q.response_text, language="text")

        if q.feedback:
            with st.expander("Grader Feedback"):
                st.write(q.feedback)

        for msg in q.validation_messages:
            if msg.type == "error":
                st.error(f"[{msg.code}] {msg.message}")
            else:
                st.warning(f"[{msg.code}] {msg.message}")

        st.divider()

    with st.form(key=f"review_action_form_{view.submission_id}"):
        current_note = st.text_area(
            "Reviewer Note",
            value=st.session_state.get(_NOTE_INPUT, view.review_note or ""),
            key=f"review_note_area_{view.submission_id}",
            placeholder="Optional note for needs-correction or approval...",
        )
        st.session_state[_NOTE_INPUT] = current_note

        # Action buttons
        col1, col2, col3 = st.columns(3)
        needs_corr = col1.form_submit_button(
            "⚠️ Mark Needs Correction",
            use_container_width=True,
        )
        approve = col2.form_submit_button(
            "✅ Approve Review",
            use_container_width=True,
        )
        return_grading = col3.form_submit_button(
            "↩️ Return to Grading",
            use_container_width=True,
        )

    return needs_corr, approve, return_grading, current_note


def main() -> None:
    configure_page("Review")
    require_authentication()
    require_page_access_safe("Review")
    render_app_header()
    st.subheader("📋 Review and Validation")
    st.caption("Review graded submissions and approve validated work.")

    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    factory = create_session_factory(engine)

    # Step 1 — Select material
    with session_scope(factory) as session:
        materials = list_materials(session, include_archived=False)
    mat_options = {m.name: m.id for m in materials} if materials else {}
    if not mat_options:
        st.info("No active materials found.")
        return
    selected_material_name = st.selectbox(
        "1. Select Material", list(mat_options.keys()), key=_SEL_MATERIAL,
    )
    material_id = mat_options[selected_material_name]

    # Step 2 — Select assessment
    with session_scope(factory) as session:
        from services.review_service import list_reviewable_assessments
        assessments = list_reviewable_assessments(session, material_id)
    if not assessments:
        st.info("No reviewable assessments found. Grade submissions first.")
        return
    ass_options = {f"{a.title} ({a.status})": a for a in assessments}
    selected_ass_label = st.selectbox(
        "2. Select Assessment", list(ass_options.keys()),
        key=_SEL_ASSESSMENT, on_change=_reset_assessment_state,
    )
    assessment = ass_options[selected_ass_label]

    # Step 3 — Progress and assessment validation
    with session_scope(factory) as session:
        progress = calculate_review_progress(session, assessment.id)
        validation_result = validate_assessment_review(session, assessment.id)
        submissions = list_review_submissions(session, assessment.id)

    _render_progress(progress)
    _render_assessment_validation(validation_result)

    if not submissions:
        st.info("No submissions found.")
        return

    # Step 4 — Submission list
    sel_sub = st.session_state.get(_SEL_SUBMISSION)
    new_sel = _render_submission_list(submissions, sel_sub)
    if new_sel:
        sel_sub = new_sel
        st.session_state[_SEL_SUBMISSION] = sel_sub

    # Step 5 — Review panel
    if sel_sub:
        with session_scope(factory) as session:
            view = get_review_submission(session, sel_sub, assessment.id)

        if view is None:
            render_safe_error("Submission not found.")
            return

        needs_corr, approve, return_grad, note = _render_review_panel(view)

        # Flag to re-run after session commits (st.rerun inside session_scope causes ROLLBACK)
        _needs_rerun = False
        _error_msg: str | None = None

        try:
            with session_scope(factory) as session:
                if needs_corr:
                    if not note or not note.strip():
                        _error_msg = "⚠️ A reviewer note is required when marking needs correction."
                    else:
                        updated = mark_submission_needs_correction(
                            session=session, submission_id=sel_sub,
                            assessment_id=assessment.id, reviewer_note=note,
                        )
                        st.success(f"✅ Submission {updated.anonymous_code} marked as needs correction.")
                        st.session_state[_NOTE_INPUT] = ""
                        _needs_rerun = True

                elif approve:
                    updated = approve_submission_review(
                        session=session, submission_id=sel_sub,
                        assessment_id=assessment.id, reviewer_note=note or None,
                    )
                    st.success(f"✅ Submission {updated.anonymous_code} approved!")
                    st.session_state[_NOTE_INPUT] = ""
                    _needs_rerun = True

                elif return_grad:
                    updated = return_submission_to_grading(
                        session=session, submission_id=sel_sub,
                        assessment_id=assessment.id,
                    )
                    st.success(f"↩️ Submission {updated.anonymous_code} returned to grading.")
                    st.session_state[_NOTE_INPUT] = ""
                    _needs_rerun = True

        except Exception as exc:
            render_safe_error(str(exc))
            logger.error("Review action error: %s", type(exc).__name__)

        if _error_msg:
            st.error(_error_msg)
        if _needs_rerun:
            st.rerun()

        # Navigation
        if view.previous_submission_id or view.next_submission_id:
            st.markdown("### Navigation")
            nc1, nc2, nc3 = st.columns([1, 2, 1])
            with nc1:
                if view.previous_submission_id:
                    if st.button("◀ Previous", use_container_width=True):
                        st.session_state[_SEL_SUBMISSION] = view.previous_submission_id
                        st.rerun()
            with nc3:
                if view.next_submission_id:
                    if st.button("Next ▶", use_container_width=True):
                        st.session_state[_SEL_SUBMISSION] = view.next_submission_id
                        st.rerun()

    logger.info(
        "Review page — assessment=%s, approved=%s/%s",
        assessment.id[:8], progress.approved, progress.total_submissions,
    )


if __name__ == "__main__":
    main()
