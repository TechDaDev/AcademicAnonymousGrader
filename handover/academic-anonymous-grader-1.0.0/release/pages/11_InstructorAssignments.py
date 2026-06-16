# Academic Anonymous Grader — Instructor Assignments Page
"""Phase 10: Instructor Assignment Management — Administrator-only page.

Capabilities:
    - Select material for filtering
    - Select assessment
    - Select one or more active Instructors
    - Create assignments
    - Deactivate active assignments
    - Reassign work
    - View active assignments
    - View historical assignments
    - Filter by Instructor, material, assessment, and status
    - Show privacy-safe progress counts

Does NOT display: student identities, responses, feedback, or individual grades.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.assignment_service import (
    deactivate_assignment,
    get_assignment_summaries,
    get_workload_summaries,
)
from services.authorization_service import AuthContext
from services.logging_service import get_logger
from services.material_service import list_materials
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import get_current_role, get_current_user_id, get_current_username, require_authentication

logger = get_logger("assignments_page")

# Session state keys
_SEL_MATERIAL = "assign_material_id"
_SEL_ASSESSMENT = "assign_assessment_id"
_SEL_INSTRUCTORS = "assign_instructor_ids"
_SHOW_HISTORY = "assign_show_history"
_FILTER_STATUS = "assign_filter_status"
_FILTER_INSTRUCTOR = "assign_filter_instructor"


def _get_auth_ctx() -> AuthContext:
    """Build AuthContext from session state."""
    return AuthContext(
        user_id=get_current_user_id() or "",
        username=get_current_username() or "",
        role=get_current_role(),
    )


def _render_create_assignment(session_factory: Any) -> None:
    """Render the create assignment form."""
    st.markdown("### ➕ Create Assignment")

    with session_scope(session_factory) as session:
        materials = list_materials(session, include_archived=False)
    if not materials:
        st.info("No active materials found.")
        return

    mat_options = {m.name: m.id for m in materials}
    sel_mat = st.selectbox(
        "Filter by Material", [""] + list(mat_options.keys()),
        key=_SEL_MATERIAL,
    )
    material_id = mat_options.get(sel_mat) if sel_mat else None

    with session_scope(session_factory) as session:
        from models.assessment import Assessment
        query = session.query(Assessment).filter(
            Assessment.finalization_status != "finalized"
        )
        if material_id:
            query = query.filter(Assessment.material_id == material_id)
        assessments = query.order_by(Assessment.title).all()

    if not assessments:
        st.info("No non-finalized assessments found.")
        return

    ass_options = {f"{a.title} ({a.material.name})": a.id for a in assessments}
    sel_ass = st.selectbox("Select Assessment", list(ass_options.keys()), key=_SEL_ASSESSMENT)
    assessment_id = ass_options.get(sel_ass)

    with session_scope(session_factory) as session:
        from models.user import User
        instructors = (
            session.query(User)
            .filter(User.role == "grader", User.is_active == True)  # noqa: E712
            .order_by(User.display_name, User.username)
            .all()
        )

    if not instructors:
        st.info("No active instructor accounts found. Create an instructor user first.")
        return

    inst_options = {
        (i.display_name or i.username): i.id for i in instructors
    }
    sel_instructors = st.multiselect(
        "Select Instructor(s)",
        list(inst_options.keys()),
        key=_SEL_INSTRUCTORS,
    )

    if st.button("Create Assignment(s)", type="primary", use_container_width=True):
        if not sel_ass or not sel_instructors or not assessment_id:
            render_safe_error("Please select an assessment and at least one instructor.")
            return

        created = 0
        errors = 0
        for inst_name in sel_instructors:
            inst_id = inst_options[inst_name]
            try:
                with session_scope(session_factory) as session:
                    from services.assignment_service import create_assignment
                    create_assignment(
                        session,
                        instructor_user_id=inst_id,
                        assessment_id=assessment_id,
                        auth_ctx=_get_auth_ctx(),
                    )
                created += 1
            except Exception as exc:
                errors += 1
                logger.warning("Assignment creation failed for %s: %s", inst_name, exc)

        if created:
            st.success(f"✅ {created} assignment(s) created successfully.")
        if errors:
            st.warning(f"⚠️ {errors} assignment(s) failed (may be duplicates or other issues).")
        st.rerun()


def _render_active_assignments(session_factory: Any) -> None:
    """Render active assignments table."""
    st.markdown("### 📋 Active Assignments")

    summaries = []
    try:
        with session_scope(session_factory) as session:
            summaries = get_assignment_summaries(
                session, auth_ctx=_get_auth_ctx(), active_only=True
            )
    except Exception as exc:
        render_safe_error(str(exc))
        return

    if not summaries:
        st.info("No active assignments found.")
        return

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        instructors = sorted(set(
            s.instructor_display_name or s.instructor_user_id[:8]
            for s in summaries
        ))
        sel_instructor = st.selectbox(
            "Filter by Instructor", ["All"] + instructors,
            key=_FILTER_INSTRUCTOR,
        )

    filtered = summaries
    if sel_instructor and sel_instructor != "All":
        filtered = [
            s for s in filtered
            if (s.instructor_display_name or s.instructor_user_id[:8]) == sel_instructor
        ]

    # Render table
    for s in filtered:
        with st.container():
            cols = st.columns([2, 2, 1, 1, 1, 1, 1, 1, 1])
            cols[0].markdown(f"**{s.instructor_display_name or s.instructor_user_id[:8]}**")
            cols[1].markdown(s.assessment_title)
            cols[2].markdown(f"`{s.material_title or '—'}`")
            cols[3].markdown(f"{s.total_submissions}")
            cols[4].markdown(f"{s.not_started}")
            cols[5].markdown(f"{s.draft}")
            cols[6].markdown(f"{s.completed}")
            cols[7].markdown(f"{s.needs_correction}")
            cols[8].markdown(f"**{s.completion_percentage}%**")

            # Action buttons
            action_col1, action_col2 = st.columns([1, 5])
            with action_col1:
                if st.button("Deactivate", key=f"deact_{s.assignment_id}",
                             use_container_width=True):
                    try:
                        with session_scope(session_factory) as session:
                            deactivate_assignment(
                                session, s.assignment_id, auth_ctx=_get_auth_ctx()
                            )
                        st.success("Assignment deactivated.")
                        st.rerun()
                    except Exception as exc:
                        render_safe_error(str(exc))
            st.divider()


def _render_assignment_history(session_factory: Any) -> None:
    """Render assignment history."""
    st.markdown("### 📜 Assignment History")

    show_history = st.checkbox("Show assignment history", key=_SHOW_HISTORY)
    if not show_history:
        return

    try:
        with session_scope(session_factory) as session:
            from services.assignment_service import get_assignment_history
            history = get_assignment_history(
                session, auth_ctx=_get_auth_ctx(), include_active=False
            )
    except Exception as exc:
        render_safe_error(str(exc))
        return

    if not history:
        st.info("No inactive assignment history found.")
        return

    for h in history:
        with st.container():
            cols = st.columns(4)
            cols[0].markdown(f"**{h.instructor.display_name or h.instructor_user_id[:8]}**")
            cols[1].markdown(h.assessment.title if h.assessment else "Deleted")
            cols[2].markdown(f"Active: {h.assigned_at.strftime('%Y-%m-%d')}")
            cols[3].markdown(
                f"Inactive: {h.unassigned_at.strftime('%Y-%m-%d') if h.unassigned_at else '—'}"
            )
            st.caption(f"Notes: {h.notes or '—'} | ID: {h.id[:8]}")
            st.divider()


def _render_workload_summary(session_factory: Any) -> None:
    """Render workload summary for all instructors."""
    st.markdown("### 📊 Instructor Workload Summary")

    try:
        with session_scope(session_factory) as session:
            workloads = get_workload_summaries(session, auth_ctx=_get_auth_ctx())
    except Exception as exc:
        render_safe_error(str(exc))
        return

    if not workloads:
        st.info("No workload data available.")
        return

    for w in workloads:
        with st.container():
            cols = st.columns(6)
            cols[0].markdown(f"**{w.instructor_display_name or w.instructor_user_id[:8]}**")
            cols[1].markdown(f"Assignments: {w.active_assignment_count}")
            cols[2].markdown(f"Total: {w.total_submissions}")
            cols[3].markdown(f"Claimed: {w.claimed_submissions}")
            cols[4].markdown(f"Completed: {w.completed_submissions}")
            cols[5].markdown(f"**{w.completion_percentage}%**")
            st.divider()


def main() -> None:
    """Page entry point."""
    configure_page("Instructor Assignments")
    require_authentication()

    # Verify administrator access
    role = get_current_role()
    if role != "administrator":
        render_safe_error("Access denied. Administrator privileges required.")
        st.stop()

    render_app_header()
    st.subheader("📌 Instructor Assignments")
    st.caption("Assign instructors to assessments and manage grading workload.")

    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    factory = create_session_factory(engine)

    tab1, tab2, tab3 = st.tabs(["Create Assignment", "Active Assignments", "Workload Summary"])

    with tab1:
        _render_create_assignment(factory)
    with tab2:
        _render_active_assignments(factory)
        _render_assignment_history(factory)
    with tab3:
        _render_workload_summary(factory)

    logger.info("Instructor Assignments page rendered.")


if __name__ == "__main__":
    main()
