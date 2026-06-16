# Academic Anonymous Grader — Academic Structure Page
"""Administrator-only page for managing academic reference data."""

from __future__ import annotations

from typing import Any

import streamlit as st
from sqlalchemy.orm import Session

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory
from services.academic_structure_service import (
    create_academic_year,
    create_department,
    create_stage,
    create_term,
    set_current_academic_year,
)
from services.academic_structure_service import (
    list_academic_years as _list_academic_years,
)
from services.academic_structure_service import (
    list_departments as _list_departments,
)
from services.academic_structure_service import (
    list_stages as _list_stages,
)
from services.academic_structure_service import (
    list_terms as _list_terms,
)
from services.audit_service import (
    ACTION_ACADEMIC_YEAR_CREATED,
    ACTION_ACADEMIC_YEAR_SET_CURRENT,
    ACTION_DEPARTMENT_CREATED,
    ACTION_STAGE_CREATED,
    ACTION_TERM_CREATED,
    record_audit_event,
)
from services.authorization_service import AuthContext, can_access_page, require_page_access
from services.logging_service import get_logger
from services.material_service import list_materials, update_material
from ui.session import get_current_role, get_current_user_id

_logger = get_logger("academic_structure_page")

st.set_page_config(page_title="Academic Structure", page_icon="🏛️", layout="wide")


def _get_session() -> Session:
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url())
    factory = create_session_factory(engine)
    return factory()


def _record(session: Session, action: str, user_id: str, metadata: dict[str, Any] | None = None) -> None:
    try:
        record_audit_event(
            session=session, action=action, user_id=user_id,
            metadata_json=metadata or {},
        )
    except Exception as exc:
        _logger.warning("Audit failed: %s", exc)


# ── Departments tab ───────────────────────────────────────────────


def _departments_tab(session: Session, ctx: AuthContext) -> None:
    st.subheader("🏫 Departments")
    col1, col2 = st.columns([3, 1])
    with col2:
        include_inactive = st.checkbox("Show archived", key="dept_archived")
    depts = _list_departments(session, include_inactive=include_inactive)
    if depts:
        data = []
        for d in depts:
            status = "🟢 Active" if d.is_active else "🔴 Archived"
            data.append({
                "Code": d.code, "Name": d.display_name,
                "Abbrev": d.abbreviation or "—", "Order": d.sort_order,
                "Status": status,
            })
        st.dataframe(data, use_container_width=True)
    with st.expander("➕ Create Department"):
        code = st.text_input("Code (lowercase, underscores)", key="dept_code").strip().lower()
        name = st.text_input("Display Name", key="dept_name").strip()
        abbrev = st.text_input("Abbreviation (optional)", key="dept_abbrev").strip() or None
        desc = st.text_area("Description (optional)", key="dept_desc").strip() or None
        order = st.number_input("Sort Order", min_value=0, value=0, key="dept_order")
        if st.button("Create Department", type="primary"):
            try:
                create_department(session, ctx, code, name, abbrev, desc, int(order))
                _record(session, ACTION_DEPARTMENT_CREATED, ctx.user_id or "",
                        {"code": code, "name": name})
                st.success(f"Department '{name}' created.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


# ── Stages tab ────────────────────────────────────────────────────


def _stages_tab(session: Session, ctx: AuthContext) -> None:
    st.subheader("📚 Stages")
    include_inactive = st.checkbox("Show archived", key="stage_archived")
    stages = _list_stages(session, include_inactive=include_inactive)
    if stages:
        data = []
        for s in stages:
            status = "🟢 Active" if s.is_active else "🔴 Archived"
            data.append({
                "Code": s.code, "Name": s.display_name,
                "Stage #": s.stage_number, "Order": s.sort_order,
                "Status": status,
            })
        st.dataframe(data, use_container_width=True)
    with st.expander("➕ Create Stage"):
        code = st.text_input("Code", key="stage_code").strip().lower()
        name = st.text_input("Display Name", key="stage_name").strip()
        num = st.number_input("Stage Number", min_value=1, max_value=4, value=1, key="stage_num")
        order = st.number_input("Sort Order", min_value=0, value=0, key="stage_order")
        if st.button("Create Stage", type="primary"):
            try:
                create_stage(session, ctx, code, name, int(num), int(order))
                _record(session, ACTION_STAGE_CREATED, ctx.user_id or "",
                        {"code": code, "name": name})
                st.success(f"Stage '{name}' created.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


# ── Terms tab ─────────────────────────────────────────────────────


def _terms_tab(session: Session, ctx: AuthContext) -> None:
    st.subheader("📅 Terms")
    include_inactive = st.checkbox("Show archived", key="term_archived")
    terms = _list_terms(session, include_inactive=include_inactive)
    if terms:
        data = []
        for t in terms:
            status = "🟢 Active" if t.is_active else "🔴 Archived"
            data.append({
                "Code": t.code, "Name": t.display_name,
                "Term #": t.term_number, "Order": t.sort_order,
                "Status": status,
            })
        st.dataframe(data, use_container_width=True)
    with st.expander("➕ Create Term"):
        code = st.text_input("Code", key="term_code").strip().lower()
        name = st.text_input("Display Name", key="term_name").strip()
        num = st.number_input("Term Number", min_value=1, max_value=2, value=1, key="term_num")
        order = st.number_input("Sort Order", min_value=0, value=0, key="term_order")
        if st.button("Create Term", type="primary"):
            try:
                create_term(session, ctx, code, name, int(num), int(order))
                _record(session, ACTION_TERM_CREATED, ctx.user_id or "",
                        {"code": code, "name": name})
                st.success(f"Term '{name}' created.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


# ── Academic Years tab ────────────────────────────────────────────


def _academic_years_tab(session: Session, ctx: AuthContext) -> None:
    st.subheader("📆 Academic Years")
    include_inactive = st.checkbox("Show archived", key="year_archived")
    years = _list_academic_years(session, include_inactive=include_inactive)
    if years:
        data = []
        for y in years:
            current = "⭐ Current" if y.is_current else ""
            status = "🟢 Active" if y.is_active else "🔴 Archived"
            data.append({
                "Code": y.code, "Name": y.display_name,
                f"{y.start_year}–{y.end_year}": "",
                "Order": y.sort_order,
                "Current": current, "Status": status,
            })
        st.dataframe(data, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Create Academic Year"):
            code = st.text_input("Code", key="year_code").strip().lower()
            name = st.text_input("Display Name (e.g. 2026–2027)", key="year_name").strip()
            sy = st.number_input("Start Year", min_value=2020, max_value=2100, value=2026, key="start_year")
            ey = st.number_input("End Year", min_value=2020, max_value=2100, value=2027, key="end_year")
            order = st.number_input("Sort Order", min_value=0, value=0, key="year_order")
            if st.button("Create Academic Year", type="primary"):
                try:
                    create_academic_year(session, ctx, code, name, int(sy), int(ey), int(order))
                    _record(session, ACTION_ACADEMIC_YEAR_CREATED, ctx.user_id or "",
                            {"code": code, "name": name})
                    st.success(f"Year '{name}' created.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with col2:
        with st.expander("⭐ Set Current Year"):
            active_years = [y for y in years if y.is_active]
            year_options = {y.display_name: y.id for y in active_years}
            if year_options:
                selected = st.selectbox("Select year", options=list(year_options.keys()), key="set_current_year")
                if st.button("Set as Current"):
                    try:
                        set_current_academic_year(session, ctx, year_options[selected])
                        _record(session, ACTION_ACADEMIC_YEAR_SET_CURRENT, (ctx.user_id if ctx else "") or "",
                                {"year_name": selected})
                        st.success(f"'{selected}' is now the current year.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.info("No active academic years available.")


# ── Main page ─────────────────────────────────────────────────────


# ── Legacy Classification Review ─────────────────────────────────


def _legacy_review_tab(session: Session, ctx: AuthContext) -> None:
    """Legacy Classification Review — resolve materials needing classification."""
    st.subheader("🔍 Legacy Classification Review")
    st.caption("Materials missing one or more classification references.")

    all_mats = list_materials(session, include_archived=True)
    review_mats = [m for m in all_mats if m.classification_needs_review]

    if not review_mats:
        st.success("All materials have complete classification references.")
        return

    st.info(f"{len(review_mats)} material(s) need classification review.")

    # Pagination
    page_size = 10
    total_pages = max(1, (len(review_mats) + page_size - 1) // page_size)
    page_key = "legacy_review_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    page = st.session_state[page_key]
    start = page * page_size
    end = start + page_size
    page_mats = review_mats[start:end]

    depts = _list_departments(session)
    stages = _list_stages(session)
    terms = _list_terms(session)
    years = _list_academic_years(session)

    for mat in page_mats:
        with st.container(border=True):
            st.write(f"**{mat.name}** ({mat.code or 'no code'})")
            legacy_info = []
            if mat.department:
                legacy_info.append(f"Dept: {mat.department}")
            if mat.stage:
                legacy_info.append(f"Stage: {mat.stage}")
            if mat.academic_year:
                legacy_info.append(f"Year: {mat.academic_year}")
            if legacy_info:
                st.caption("Legacy labels: " + " | ".join(legacy_info))
            st.caption(f"Review status: {'⚠️ Needs review' if mat.classification_needs_review else '✅ Complete'}")

            with st.form(key=f"legacy_classify_{mat.id}"):
                col1, col2 = st.columns(2)
                with col1:
                    dept_opts = [("", "-- Select --")] + [(d.id, d.display_name) for d in depts]
                    sel_dept = st.selectbox(
                        "Department",
                        options=[d[0] for d in dept_opts],
                        format_func=lambda x: next((d[1] for d in dept_opts if d[0] == x), "-- Select --"),
                        index=0,
                        key=f"legacy_dept_{mat.id}",
                    )
                    stage_opts = [("", "-- Select --")] + [(s.id, s.display_name) for s in stages]
                    sel_stage = st.selectbox(
                        "Stage",
                        options=[s[0] for s in stage_opts],
                        format_func=lambda x: next((s[1] for s in stage_opts if s[0] == x), "-- Select --"),
                        index=0,
                        key=f"legacy_stage_{mat.id}",
                    )
                with col2:
                    term_opts = [("", "-- Select --")] + [(t.id, t.display_name) for t in terms]
                    sel_term = st.selectbox(
                        "Term",
                        options=[t[0] for t in term_opts],
                        format_func=lambda x: next((t[1] for t in term_opts if t[0] == x), "-- Select --"),
                        index=0,
                        key=f"legacy_term_{mat.id}",
                    )
                    year_opts = [("", "-- Select --")] + [(y.id, y.display_name) for y in years]
                    sel_year = st.selectbox(
                        "Academic Year",
                        options=[y[0] for y in year_opts],
                        format_func=lambda x: next((y[1] for y in year_opts if y[0] == x), "-- Select --"),
                        index=0,
                        key=f"legacy_year_{mat.id}",
                    )

                if st.form_submit_button("Save Classification"):
                    try:
                        result = update_material(
                            session, mat.id,
                            department_id=sel_dept or None,
                            academic_stage_id=sel_stage or None,
                            academic_term_id=sel_term or None,
                            academic_year_id=sel_year or None,
                        )
                        _record(session, "material_classification_updated", ctx.user_id or "",
                                {"material_id": mat.id, "material_name": mat.name})
                        st.success(f"Classification saved for '{result.name}'.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    # Pagination controls
    if total_pages > 1:
        col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
        with col1:
            if page > 0 and st.button("◀ Previous"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with col3:
            st.write(f"Page {page + 1} of {total_pages}")
        with col4:
            if page < total_pages - 1 and st.button("Next ▶"):
                st.session_state[page_key] = page + 1
                st.rerun()


# ── Main page ─────────────────────────────────────────────────────


def main() -> None:
    ctx_role = get_current_role()
    user_id = get_current_user_id()

    if not can_access_page(ctx_role, "AcademicStructure"):
        require_page_access(ctx_role, "AcademicStructure")
        return

    ctx = AuthContext(user_id=user_id or "", role=ctx_role, username="")
    if not ctx.user_id:
        require_page_access(ctx_role, "AcademicStructure")
        return

    session = _get_session()
    try:
        st.title("🏛️ Academic Structure")
        st.caption("Manage departments, stages, terms, and academic years.")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Departments", "Stages", "Terms", "Academic Years",
            "Legacy Review",
        ])

        with tab1:
            _departments_tab(session, ctx)
        with tab2:
            _stages_tab(session, ctx)
        with tab3:
            _terms_tab(session, ctx)
        with tab4:
            _academic_years_tab(session, ctx)
        with tab5:
            _legacy_review_tab(session, ctx)

    finally:
        session.close()


if __name__ == "__main__":
    main()
