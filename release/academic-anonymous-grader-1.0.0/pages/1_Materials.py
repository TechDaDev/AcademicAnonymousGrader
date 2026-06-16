# Academic Anonymous Grader — Materials Page
"""Material management — create, view, edit, archive, restore materials."""

from __future__ import annotations

import streamlit as st
from sqlalchemy.orm import Session

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory
from services.exceptions import DuplicateMaterialError, MaterialNotFoundError, MaterialValidationError
from services.logging_service import get_logger
from services.material_service import (
    archive_material,
    create_material,
    get_material,
    list_materials,
    restore_material,
    update_material,
)
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import require_authentication, require_page_access_safe

logger = get_logger("materials_page")

_SEL = "mat_selected_id"
_EDIT = "mat_edit_id"
_ARCHIVE_CONFIRM = "mat_archive_confirm"


def _get_session() -> Session:
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    initialize_database(engine)
    factory = create_session_factory(engine)
    return factory()


def _reset_state() -> None:
    for key in (_SEL, _EDIT, _ARCHIVE_CONFIRM):
        st.session_state.pop(key, None)


def _refresh() -> None:
    st.rerun()


def _render_create(session: Session) -> None:
    from services.academic_structure_service import (
        get_classification_options,
        get_current_academic_year,
    )

    opts = get_classification_options(session)
    current_year = get_current_academic_year(session)

    with st.expander("➕ Create New Material", expanded=False):
        with st.form("create_material_form"):
            name = st.text_input("Name *")
            code = st.text_input("Code")

            dept_options = [("", "-- Select Department --")] + [
                (d.id, d.display_name) for d in opts["departments"]
            ]
            dept_id = st.selectbox(
                "Department *",
                options=[d[0] for d in dept_options],
                format_func=lambda x: next((d[1] for d in dept_options if d[0] == x), "-- Select Department --"),
                key="mat_create_dept",
            )

            stage_options = [("", "-- Select Stage --")] + [
                (s.id, s.display_name) for s in opts["stages"]
            ]
            stage_id = st.selectbox(
                "Stage *",
                options=[s[0] for s in stage_options],
                format_func=lambda x: next((s[1] for s in stage_options if s[0] == x), "-- Select Stage --"),
                key="mat_create_stage",
            )

            term_options = [("", "-- Select Term --")] + [
                (t.id, t.display_name) for t in opts["terms"]
            ]
            term_id = st.selectbox(
                "Term *",
                options=[t[0] for t in term_options],
                format_func=lambda x: next((t[1] for t in term_options if t[0] == x), "-- Select Term --"),
                key="mat_create_term",
            )

            year_options = [("", "-- Select Academic Year --")] + [
                (y.id, y.display_name) for y in opts["academic_years"]
            ]
            current_year_id = current_year.id if current_year else ""
            year_id_default = current_year_id if any(y[0] == current_year_id for y in year_options) else ""
            year_id = st.selectbox(
                "Academic Year *",
                options=[y[0] for y in year_options],
                format_func=lambda x: next((y[1] for y in year_options if y[0] == x), "-- Select Academic Year --"),
                index=0 if not year_id_default else next(
                    (i for i, y in enumerate(year_options) if y[0] == year_id_default), 0
                ),
                key="mat_create_year",
            )

            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Create Material")
            if submitted:
                if not dept_id or not stage_id or not term_id or not year_id:
                    st.error("All classification fields (Department, Stage, Term, Academic Year) are required.")
                    return
                try:
                    result = create_material(
                        session, name=name, code=code or None,
                        notes=notes or None,
                        department_id=dept_id,
                        academic_stage_id=stage_id,
                        academic_term_id=term_id,
                        academic_year_id=year_id,
                    )
                    session.commit()
                    st.success(f"Material '{result.name}' created successfully.")
                    _reset_state()
                    _refresh()
                except (MaterialValidationError, DuplicateMaterialError) as exc:
                    st.error(str(exc))
                    session.rollback()


def _render_edit_form(session: Session, material_id: str) -> None:
    from services.academic_structure_service import (
        list_academic_years,
        list_departments,
        list_stages,
        list_terms,
    )

    try:
        mat = get_material(session, material_id)
    except MaterialNotFoundError:
        render_safe_error("Material not found.")
        _reset_state()
        return

    st.subheader(f"Edit: {mat.name}")
    with st.form("edit_material_form"):
        name = st.text_input("Name *", value=mat.name)
        code = st.text_input("Code", value=mat.code or "")
        notes = st.text_area("Notes", value=mat.notes or "")

        # Classification dropdowns with archived reference support
        all_depts = list_departments(session, include_inactive=True)
        dept_options = [("", "-- Select Department --")] + [
            (d.id, d.display_name + (" (Archived)" if not d.is_active else ""))
            for d in all_depts
        ]
        dept_default = mat.department_id or ""
        dept_idx = next((i for i, d in enumerate(dept_options) if d[0] == dept_default), 0)
        dept_id = st.selectbox(
            "Department *",
            options=[d[0] for d in dept_options],
            format_func=lambda x: next((d[1] for d in dept_options if d[0] == x), "-- Select Department --"),
            index=dept_idx,
            key="mat_edit_dept",
        )

        all_stages = list_stages(session, include_inactive=True)
        stage_options = [("", "-- Select Stage --")] + [
            (s.id, s.display_name + (" (Archived)" if not s.is_active else ""))
            for s in all_stages
        ]
        stage_default = mat.academic_stage_id or ""
        stage_idx = next((i for i, s in enumerate(stage_options) if s[0] == stage_default), 0)
        stage_id = st.selectbox(
            "Stage *",
            options=[s[0] for s in stage_options],
            format_func=lambda x: next((s[1] for s in stage_options if s[0] == x), "-- Select Stage --"),
            index=stage_idx,
            key="mat_edit_stage",
        )

        all_terms = list_terms(session, include_inactive=True)
        term_options = [("", "-- Select Term --")] + [
            (t.id, t.display_name + (" (Archived)" if not t.is_active else ""))
            for t in all_terms
        ]
        term_default = mat.academic_term_id or ""
        term_idx = next((i for i, t in enumerate(term_options) if t[0] == term_default), 0)
        term_id = st.selectbox(
            "Term *",
            options=[t[0] for t in term_options],
            format_func=lambda x: next((t[1] for t in term_options if t[0] == x), "-- Select Term --"),
            index=term_idx,
            key="mat_edit_term",
        )

        all_years = list_academic_years(session, include_inactive=True)
        year_options = [("", "-- Select Academic Year --")] + [
            (y.id, y.display_name + (" (Archived)" if not y.is_active else ""))
            for y in all_years
        ]
        year_default = mat.academic_year_id or ""
        year_idx = next((i for i, y in enumerate(year_options) if y[0] == year_default), 0)
        year_id = st.selectbox(
            "Academic Year *",
            options=[y[0] for y in year_options],
            format_func=lambda x: next((y[1] for y in year_options if y[0] == x), "-- Select Academic Year --"),
            index=year_idx,
            key="mat_edit_year",
        )

        col1, col2 = st.columns(2)
        with col1:
            saved = st.form_submit_button("💾 Save Changes")
        with col2:
            cancelled = st.form_submit_button("Cancel")
        if saved:
            try:
                update_material(
                    session, material_id, name=name, code=code or None,
                    notes=notes or None,
                    department_id=dept_id or None,
                    academic_stage_id=stage_id or None,
                    academic_term_id=term_id or None,
                    academic_year_id=year_id or None,
                )
                session.commit()
                st.success("Material updated.")
                _reset_state()
                _refresh()
            except (MaterialValidationError, DuplicateMaterialError) as exc:
                st.error(str(exc))
                session.rollback()
        if cancelled:
            _reset_state()
            _refresh()


def _render_material_row(
    session: Session, mat_id: str, name: str, code: str | None,
    year: str | None, stage: str | None, dept: str | None,
    assess_count: int, is_archived: bool, updated: str | None,
) -> None:
    cols = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1, 0.8, 0.8, 0.4, 0.4])
    cols[0].write(name)
    cols[1].write(code or "—")
    cols[2].write(year or "—")
    cols[3].write(stage or "—")
    cols[4].write(dept or "—")
    cols[5].write(str(assess_count))
    cols[6].write("📦 Archived" if is_archived else "✅ Active")
    cols[7].write(updated[:10] if updated else "—")

    if cols[8].button("✏️", key=f"edit_{mat_id}"):
        st.session_state[_EDIT] = mat_id
        _refresh()

    if not is_archived:
        if cols[9].button("📦", key=f"arch_{mat_id}"):
            st.session_state[_ARCHIVE_CONFIRM] = mat_id
            _refresh()
    else:
        if cols[9].button("♻️", key=f"rest_{mat_id}"):
            try:
                restore_material(session, mat_id)
                session.commit()
                st.success(f"Material '{name}' restored.")
                _refresh()
            except MaterialNotFoundError as exc:
                st.error(str(exc))
                session.rollback()


def _render_archive_confirm(session: Session) -> None:
    mat_id = st.session_state.get(_ARCHIVE_CONFIRM)
    if not mat_id:
        return
    try:
        mat = get_material(session, mat_id)
    except MaterialNotFoundError:
        return
    st.warning(f"Are you sure you want to archive '{mat.name}'?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Yes, Archive"):
        try:
            archive_material(session, mat_id)
            session.commit()
            st.success(f"Material '{mat.name}' archived.")
            _reset_state()
            _refresh()
        except MaterialNotFoundError as exc:
            st.error(str(exc))
            session.rollback()
    if col2.button("❌ Cancel"):
        _reset_state()
        _refresh()


def main() -> None:
    """Materials management page."""
    configure_page("Materials")
    require_authentication()
    require_page_access_safe("Materials")
    render_app_header()
    st.subheader("📦 Materials")

    session = _get_session()

    if st.session_state.get(_ARCHIVE_CONFIRM):
        _render_archive_confirm(session)
        session.close()
        return

    edit_id = st.session_state.get(_EDIT)
    if edit_id:
        _render_edit_form(session, edit_id)
        session.close()
        return

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 Search by name or code")
    with col2:
        show_archived = st.checkbox("Show Archived")
    with col3:
        all_mats = list_materials(session, include_archived=True)
        st.write(f"**Total:** {len(all_mats)}")

    _render_create(session)

    materials = list_materials(session, include_archived=show_archived, search_query=search or None)

    if not materials:
        st.info("No materials found. Create your first material above.")
        session.close()
        return

    cols = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1, 0.8, 0.8, 0.4, 0.4])
    cols[0].write("**Name**")
    cols[1].write("**Code**")
    cols[2].write("**Year**")
    cols[3].write("**Stage**")
    cols[4].write("**Dept**")
    cols[5].write("**#Assess**")
    cols[6].write("**Status**")
    cols[7].write("**Updated**")
    cols[8].write("**Edit**")
    cols[9].write("**Arch**")
    st.divider()

    for m in materials:
        _render_material_row(
            session, m.id, m.name, m.code, m.academic_year,
            m.stage, m.department, m.assessment_count,
            m.is_archived, m.updated_at,
        )

    session.close()


if __name__ == "__main__":
    main()
