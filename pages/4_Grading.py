# Academic Anonymous Grader — Grading Page
"""Phase 5: Manual Anonymous Grading — grade imported submissions without seeing identities."""

from __future__ import annotations

from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.grading_service import (
    GradingProgress,
    SubmissionGradingView,
    calculate_grading_progress,
    get_grading_submission,
    list_anonymous_submissions,
    save_submission_grades,
)
from services.logging_service import get_logger
from services.material_service import list_materials
from ui.layout import configure_page, render_app_header, render_safe_error

logger = get_logger("grading_page")

# ── Session state keys ────────────────────────────────────────────
_SEL_MATERIAL = "grading_material_id"
_SEL_ASSESSMENT = "grading_assessment_id"
_SEL_SUBMISSION = "grading_submission_id"
_FILTER = "grading_filter"
_GRADE_INPUTS = "grading_grade_inputs"
_FEEDBACK_INPUTS = "grading_feedback_inputs"
_DIRTY = "grading_dirty"
_NAV_PENDING = "grading_nav_pending"


def _reset_assessment_state() -> None:
    """Clear grading state when assessment changes."""
    for key in [_SEL_SUBMISSION, _GRADE_INPUTS, _FEEDBACK_INPUTS, _DIRTY, _NAV_PENDING]:
        if key in st.session_state:
            del st.session_state[key]


def _load_saved_values(view: SubmissionGradingView) -> dict[str, str]:
    """Load saved grade/feedback from the view into session state."""
    grades: dict[str, str] = {}
    feedbacks: dict[str, str | None] = {}
    for q in view.questions:
        grades[q.question_id] = str(q.grade) if q.grade is not None else ""
        feedbacks[q.question_id] = q.feedback
    st.session_state[_GRADE_INPUTS] = grades
    st.session_state[_FEEDBACK_INPUTS] = feedbacks
    st.session_state[_DIRTY] = False
    return grades


def _render_progress(progress: GradingProgress) -> None:
    """Render grading progress metrics."""
    st.markdown("### Grading Progress")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", progress.total_submissions)
    c2.metric("Ungraded", progress.ungraded_submissions)
    c3.metric("In Progress", progress.in_progress_submissions)
    c4.metric("Graded", progress.completed_submissions)
    c5.metric("Completion", f"{progress.completion_percentage}%")


def _render_submission_list(
    submissions: list[Any],
    current_submission_id: str | None,
) -> str | None:
    """Render the submission sidebar and return newly selected submission ID."""
    st.markdown("### Submissions")
    selected_filter = st.radio(
        "Filter",
        ["All", "Ungraded", "In progress", "Graded"],
        key=_FILTER,
        horizontal=True,
    )

    filter_map = {
        "All": "all",
        "Ungraded": "ungraded",
        "In progress": "in_progress",
        "Graded": "graded",
    }
    filtered = [
        s for s in submissions
        if s.submission_status == filter_map[selected_filter] or selected_filter == "All"
    ]

    for s in filtered:
        sub_id: str = s.submission_id
        label = (
            f"{s.anonymous_code} — "
            f"{s.graded_question_count}/{s.total_question_count} "
            f"({s.current_total}/{s.maximum_total})"
        )
        if s.submission_status == "graded":
            label += " ✅"
        elif s.submission_status == "in_progress":
            label += " 🔄"
        else:
            label += " ⬜"

        btn_key = f"sub_btn_{sub_id}"
        if st.button(label, key=btn_key, use_container_width=True):
            if st.session_state.get(_DIRTY):
                st.session_state[_NAV_PENDING] = sub_id
                st.rerun()
            else:
                return sub_id

    return None


def _render_grading_panel(view: SubmissionGradingView) -> tuple[bool, bool]:
    """Render the grading UI for a submission. Returns (save_draft_clicked, mark_graded_clicked)."""
    st.markdown(f"### Submission: {view.anonymous_code}")
    st.caption(f"Assessment: {view.assessment_title}")
    st.caption(f"Total: {view.current_total} / {view.maximum_total}")

    # Review badge
    rs = view.review_status
    if rs == "approved":
        st.success("✅ **Approved** — This submission has been reviewed and approved.")
    elif rs == "needs_correction":
        st.warning(f"⚠️ **Needs Correction** — Reviewer note: {view.review_note or '(none)'}")
    elif rs == "ready_for_review":
        st.info("📋 **Ready for Review** — All questions graded, awaiting review.")
    else:
        st.caption("*(Not reviewed)*")

    grade_inputs = st.session_state.get(_GRADE_INPUTS, {})
    feedback_inputs = st.session_state.get(_FEEDBACK_INPUTS, {})

    with st.form(key=f"grading_form_{view.submission_id}"):
        for q in view.questions:
            st.markdown(f"#### Question {q.question_number}: {q.question_title or ''}")
            st.caption(f"Maximum grade: {q.maximum_grade}")

            # Response display
            if q.is_blank:
                st.caption("*(blank response)*")
            elif q.response_text:
                st.code(q.response_text, language="text")
            else:
                st.caption("*(no response)*")

            # Grade input
            current_grade = grade_inputs.get(q.question_id, "")
            grade_val = st.text_input(
                f"Grade (max {q.maximum_grade})",
                value=current_grade,
                key=f"grade_{q.question_id}",
                placeholder=f"0.00 - {q.maximum_grade}",
            )
            grade_inputs[q.question_id] = grade_val

            # Feedback input
            current_fb = feedback_inputs.get(q.question_id, "")
            fb_val = st.text_area(
                "Feedback (optional)",
                value=current_fb or "",
                key=f"fb_{q.question_id}",
                placeholder="Enter grader comments...",
            )
            feedback_inputs[q.question_id] = fb_val

            st.divider()

        st.session_state[_GRADE_INPUTS] = grade_inputs
        st.session_state[_FEEDBACK_INPUTS] = feedback_inputs

        col1, col2 = st.columns(2)
        save_draft = col1.form_submit_button("💾 Save Draft", use_container_width=True)
        mark_graded = col2.form_submit_button("✅ Mark Submission Graded", use_container_width=True)

        if save_draft or mark_graded:
            st.session_state[_DIRTY] = False

        return (save_draft, mark_graded)

    return (False, False)


def main() -> None:
    configure_page("Grading")
    render_app_header()
    st.subheader("✏️ Anonymous Grading")
    st.caption("Grade imported submissions without seeing student identities.")

    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    factory = create_session_factory(engine)

    # Step 1 — Select material
    with session_scope(factory) as session:
        materials = list_materials(session, include_archived=False)
    mat_options = {m.name: m.id for m in materials} if materials else {}
    if not mat_options:
        st.info("No active materials found. Create a material first.")
        return

    selected_material_name = st.selectbox(
        "1. Select Material",
        list(mat_options.keys()),
        key=_SEL_MATERIAL,
    )
    material_id = mat_options[selected_material_name]

    # Step 2 — Select assessment
    with session_scope(factory) as session:
        from services.grading_service import list_gradable_assessments
        assessments = list_gradable_assessments(session, material_id)
    if not assessments:
        st.info("No gradable assessments found. Import submissions first.")
        return
    ass_options = {f"{a.title} ({a.status})": a for a in assessments}
    selected_ass_label = st.selectbox(
        "2. Select Assessment",
        list(ass_options.keys()),
        key=_SEL_ASSESSMENT,
        on_change=_reset_assessment_state,
    )
    assessment = ass_options[selected_ass_label]

    # Step 3 — Progress
    with session_scope(factory) as session:
        progress = calculate_grading_progress(session, assessment.id)
        submissions = list_anonymous_submissions(session, assessment.id)

    _render_progress(progress)

    if not submissions:
        st.info("No submissions found for this assessment. Import submissions first.")
        return

    # Step 4 — Submission list and selection
    sel_sub = st.session_state.get(_SEL_SUBMISSION)

    # Handle pending navigation after dirty save
    pending_nav = st.session_state.get(_NAV_PENDING)
    if pending_nav:
        sel_sub = pending_nav
        st.session_state[_SEL_SUBMISSION] = sel_sub
        st.session_state[_NAV_PENDING] = None

    new_sel = _render_submission_list(submissions, sel_sub)
    if new_sel:
        sel_sub = new_sel
        st.session_state[_SEL_SUBMISSION] = sel_sub

    # Step 5 — Grading panel
    if sel_sub:
        with session_scope(factory) as session:
            view = get_grading_submission(session, sel_sub, assessment.id)

        if view is None:
            render_safe_error("Submission not found.")
            return

        # Load saved values on first display
        if not st.session_state.get(_GRADE_INPUTS):
            _load_saved_values(view)
        elif st.session_state.get(_NAV_PENDING):
            _load_saved_values(view)

        # Render grading panel — buttons return True/False
        save_draft_clicked, mark_graded_clicked = _render_grading_panel(view)
        save_clicked = save_draft_clicked or mark_graded_clicked

        if save_clicked:
            grade_inputs = st.session_state.get(_GRADE_INPUTS, {})
            feedback_inputs = st.session_state.get(_FEEDBACK_INPUTS, {})

            all_filled = all(
                v.strip() != "" for v in grade_inputs.values()
            )
            marking = mark_graded_clicked

            try:
                with session_scope(factory) as session:
                    updated_view = save_submission_grades(
                        session=session,
                        submission_id=sel_sub,
                        assessment_id=assessment.id,
                        grades=grade_inputs,
                        feedbacks=feedback_inputs,
                        marking_graded=marking and all_filled,
                    )
                _load_saved_values(updated_view)
                if marking and all_filled:
                    msg = (f"✅ Submission {view.anonymous_code} marked as graded! "
                           f"Total: {updated_view.current_total}/{updated_view.maximum_total}")
                    st.success(msg)
                else:
                    st.success("💾 Draft saved.")
                st.rerun()
            except Exception as exc:
                render_safe_error(str(exc))
                logger.error("Grade save error: %s", type(exc).__name__)

        # Navigation
        if view.previous_submission_id or view.next_submission_id:
            st.markdown("### Navigation")
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            with nav_col1:
                if view.previous_submission_id:
                    if st.button("◀ Previous", use_container_width=True):
                        if st.session_state.get(_DIRTY):
                            st.session_state[_NAV_PENDING] = view.previous_submission_id
                            st.rerun()
                        else:
                            _reset_assessment_state()
                            st.session_state[_SEL_SUBMISSION] = view.previous_submission_id
                            st.rerun()
            with nav_col3:
                if view.next_submission_id:
                    if st.button("Next ▶", use_container_width=True):
                        if st.session_state.get(_DIRTY):
                            st.session_state[_NAV_PENDING] = view.next_submission_id
                            st.rerun()
                        else:
                            _reset_assessment_state()
                            st.session_state[_SEL_SUBMISSION] = view.next_submission_id
                            st.rerun()

    logger.info(
        "Grading page — assessment=%s, submissions=%s, progress=%s",
        assessment.id[:8],
        progress.total_submissions,
        f"{progress.completed_submissions}/{progress.total_submissions}",
    )


if __name__ == "__main__":
    main()
