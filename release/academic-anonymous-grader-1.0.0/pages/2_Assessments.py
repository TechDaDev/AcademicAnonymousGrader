# Academic Anonymous Grader — Assessments Page
"""Assessment and question management."""

from __future__ import annotations

from decimal import Decimal

import streamlit as st
from sqlalchemy.orm import Session

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory
from services.assessment_service import (
    archive_assessment,
    create_assessment,
    duplicate_assessment,
    get_assessment,
    list_assessments,
    mark_assessment_ready,
    restore_assessment,
    return_assessment_to_draft,
    update_assessment,
)
from services.exceptions import (
    AssessmentNotFoundError,
    AssessmentValidationError,
    InvalidAssessmentStateError,
    QuestionDeletionBlockedError,
    QuestionValidationError,
)
from services.logging_service import get_logger
from services.material_service import list_materials
from services.question_service import (
    create_question,
    delete_question,
    list_questions,
    reorder_questions,
    update_question,
)
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import require_authentication, require_page_access_safe

logger = get_logger("assessments_page")

_SEL_ASSESS = "as_sel_id"
_EDIT_ASSESS = "as_edit_id"
_EDIT_Q = "as_edit_qid"
_ARCHIVE_CONFIRM = "as_archive_id"
_SEL_MAT = "as_sel_mat"
_DUP_CONFIRM = "as_dup_id"


def _get_session() -> Session:
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    initialize_database(engine)
    factory = create_session_factory(engine)
    return factory()


def _reset_state() -> None:
    for key in (_SEL_ASSESS, _EDIT_ASSESS, _EDIT_Q, _ARCHIVE_CONFIRM, _SEL_MAT, _DUP_CONFIRM):
        st.session_state.pop(key, None)


def _refresh() -> None:
    st.rerun()


def _fmt(d: Decimal) -> str:
    return f"{d:.2f}"


def _render_create_assessment(session: Session, material_id: str) -> None:
    with st.expander("➕ Create New Assessment", expanded=False):
        with st.form("create_assessment_form"):
            title = st.text_input("Title *")
            atype = st.text_input("Assessment Type")
            year = st.text_input("Academic Year")
            max_grade = st.text_input("Maximum Grade *", value="100.00")
            submitted = st.form_submit_button("Create Assessment")
            if submitted:
                try:
                    result = create_assessment(
                        session, material_id=material_id, title=title,
                        assessment_type=atype or None, academic_year=year or None,
                        maximum_grade=max_grade,
                    )
                    session.commit()
                    st.success(f"Assessment '{result.title}' created.")
                    _reset_state()
                    _refresh()
                except AssessmentValidationError as exc:
                    st.error(str(exc))
                    session.rollback()


def _render_assessment_detail(session: Session, assessment_id: str) -> None:
    try:
        a = get_assessment(session, assessment_id)
    except AssessmentNotFoundError:
        render_safe_error("Assessment not found.")
        return

    st.subheader(f"📝 {a.title}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", a.status)
    col2.metric("Max Grade", _fmt(a.maximum_grade))
    col3.metric("Question Total", _fmt(a.question_total))
    diff = a.maximum_grade - a.question_total
    col4.metric("Difference", _fmt(diff))

    if a.is_valid:
        st.success(a.validation_message)
    else:
        st.warning(a.validation_message)

    # ── Actions ──
    actions = []
    can_edit = a.status in ("draft", "ready")

    if a.status == "draft":
        if a.question_count > 0 and a.is_valid:
            actions.append(("🚀 Mark Ready", "ready"))
        else:
            st.info("Add questions whose total matches the maximum grade to mark as Ready.")
    elif a.status == "ready":
        actions.append(("🔙 Return to Draft", "draft"))
    elif a.status == "archived":
        actions.append(("♻️ Restore", "restore"))

    if can_edit:
        actions.append(("📦 Archive", "archive"))
        actions.append(("📋 Duplicate", "duplicate"))

    for label, action in actions:
        if st.button(label, key=f"as_action_{action}_{assessment_id}"):
            try:
                if action == "ready":
                    mark_assessment_ready(session, assessment_id)
                    session.commit()
                    st.success("Assessment marked as Ready.")
                elif action == "draft":
                    return_assessment_to_draft(session, assessment_id)
                    session.commit()
                    st.success("Assessment returned to Draft.")
                elif action == "archive":
                    archive_assessment(session, assessment_id)
                    session.commit()
                    st.success("Assessment archived.")
                elif action == "restore":
                    restore_assessment(session, assessment_id)
                    session.commit()
                    st.success("Assessment restored.")
                elif action == "duplicate":
                    dup = duplicate_assessment(session, assessment_id)
                    session.commit()
                    st.success(f"Duplicated as '{dup.title}'.")
                _reset_state()
                _refresh()
            except (AssessmentValidationError, InvalidAssessmentStateError) as exc:
                st.error(str(exc))
                session.rollback()

    st.divider()

    # ── Edit assessment fields ──
    if can_edit:
        st.subheader("Edit Assessment Settings")
        with st.form("edit_assessment_form"):
            etitle = st.text_input("Title", value=a.title)
            etype = st.text_input("Type", value=a.assessment_type or "")
            eyear = st.text_input("Year", value=a.academic_year or "")
            emax = st.text_input("Maximum Grade", value=_fmt(a.maximum_grade))
            if st.form_submit_button("💾 Update Settings"):
                try:
                    update_assessment(
                        session, assessment_id, title=etitle,
                        assessment_type=etype or None, academic_year=eyear or None,
                        maximum_grade=emax,
                    )
                    session.commit()
                    st.success("Assessment updated.")
                    _refresh()
                except (AssessmentValidationError, InvalidAssessmentStateError) as exc:
                    st.error(str(exc))
                    session.rollback()

    st.divider()

    # ── Questions ──
    st.subheader("Questions")
    questions = list_questions(session, assessment_id)

    if can_edit:
        with st.expander("➕ Add Question", expanded=False):
            with st.form("add_question_form"):
                qnum = st.number_input("Question Number", min_value=1, step=1, value=len(questions) + 1)
                qtitle = st.text_input("Title (optional)")
                qmax = st.text_input("Maximum Grade", value="10.00")
                qrubric = st.text_area("Rubric (optional)")
                if st.form_submit_button("Add Question"):
                    try:
                        create_question(
                            session, assessment_id, question_number=int(qnum),
                            maximum_grade=qmax, title=qtitle or None, rubric=qrubric or None,
                        )
                        session.commit()
                        st.success("Question added.")
                        _refresh()
                    except (QuestionValidationError, InvalidAssessmentStateError) as exc:
                        st.error(str(exc))
                        session.rollback()

    # Question list
    if not questions:
        st.info("No questions configured.")
    else:
        for q in questions:
            cols = st.columns([1, 3, 1.5, 0.5, 0.5])
            cols[0].write(f"**#{q.question_number}**")
            cols[1].write(q.title or "—")
            cols[2].write(f"Max: {_fmt(q.maximum_grade)}")
            if can_edit:
                if cols[3].button("✏️", key=f"edit_q_{q.id}"):
                    st.session_state[_EDIT_Q] = q.id
                    _refresh()
                if cols[4].button("🗑️", key=f"del_q_{q.id}"):
                    try:
                        delete_question(session, q.id)
                        session.commit()
                        st.success(f"Question #{q.question_number} deleted.")
                        _refresh()
                    except (InvalidAssessmentStateError, QuestionDeletionBlockedError) as exc:
                        st.error(str(exc))
                        session.rollback()

    # ── Edit single question ──
    edit_qid = st.session_state.get(_EDIT_Q)
    if edit_qid:
        edit_q = next((q for q in questions if q.id == edit_qid), None)
        if edit_q:
            st.subheader(f"Edit Question #{edit_q.question_number}")
            with st.form("edit_question_form"):
                eqnum = st.number_input("Number", value=edit_q.question_number, min_value=1, step=1)
                eqtitle = st.text_input("Title", value=edit_q.title or "")
                eqmax = st.text_input("Maximum Grade", value=_fmt(edit_q.maximum_grade))
                eqrubric = st.text_area("Rubric", value=edit_q.rubric or "")
                col1, col2 = st.columns(2)
                if col1.form_submit_button("💾 Save"):
                    try:
                        update_question(
                            session, edit_qid, question_number=int(eqnum),
                            maximum_grade=eqmax, title=eqtitle or None, rubric=eqrubric or None,
                        )
                        session.commit()
                        st.success("Question updated.")
                        st.session_state.pop(_EDIT_Q, None)
                        _refresh()
                    except (QuestionValidationError, InvalidAssessmentStateError) as exc:
                        st.error(str(exc))
                        session.rollback()
                if col2.form_submit_button("Cancel"):
                    st.session_state.pop(_EDIT_Q, None)
                    _refresh()

    # ── Reorder ──
    if can_edit and len(questions) > 1:
        st.subheader("Reorder Questions")
        selected_order: list[str] = []
        for q in questions:
            if st.checkbox(f"#{q.question_number} {q.title or ''}", value=True, key=f"reord_{q.id}"):
                selected_order.append(q.id)
        if selected_order and st.button("Apply New Order"):
            reorder_questions(session, assessment_id, selected_order)
            session.commit()
            st.success("Questions reordered.")
            _refresh()


def main() -> None:
    """Assessments management page."""
    configure_page("Assessments")
    require_authentication()
    require_page_access_safe("Assessments")
    render_app_header()
    st.subheader("📝 Assessments")

    session = _get_session()

    # ── Material selector ──
    materials = list_materials(session, include_archived=False)
    mat_options = {m.name: m.id for m in materials}
    if not mat_options:
        st.info("No active materials found. Create a material first on the Materials page.")
        session.close()
        return

    sel_mat_name = st.selectbox(
        "Select Material",
        options=list(mat_options.keys()),
        key="mat_selector",
    )
    material_id = mat_options[sel_mat_name]

    # ── Create assessment ──
    _render_create_assessment(session, material_id)

    # ── Assessment list ──
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("🔍 Search assessments")
    with col2:
        status_filter = st.selectbox("Status", ["all", "draft", "ready", "archived"])

    assessments = list_assessments(
        session, material_id=material_id,
        status_filter=status_filter,
        include_archived=True,
        search_query=search or None,
    )

    if not assessments:
        st.info("No assessments found for this material.")
        session.close()
        return

    for a in assessments:
        diff = a.maximum_grade - a.question_total
        with st.container():
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2.5, 1, 1, 1, 0.8, 0.8, 0.8, 0.5])
            c1.write(f"**{a.title}**")
            c2.write(a.status)
            c3.write(f"Max: {_fmt(a.maximum_grade)}")
            c4.write(f"Q: {a.question_count}")
            c5.write(f"∑: {_fmt(a.question_total)}")
            c6.write(f"Δ: {_fmt(diff)}")
            c7.write("✅" if a.is_valid else "⚠️")
            if c8.button("Open", key=f"open_{a.id}"):
                st.session_state[_SEL_ASSESS] = a.id
                _refresh()

    # ── Selected assessment detail ──
    sel_id = st.session_state.get(_SEL_ASSESS)
    if sel_id:
        st.divider()
        _render_assessment_detail(session, sel_id)

    session.close()


if __name__ == "__main__":
    main()
