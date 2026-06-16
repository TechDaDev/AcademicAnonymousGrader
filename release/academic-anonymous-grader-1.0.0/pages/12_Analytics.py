# Academic Anonymous Grader — Analytics Page
"""Privacy-safe analytics and reporting page.

Role-aware tabs: Administrator sees all tabs; Instructor (grader) sees
only their own analytics tabs. All data is aggregated and anonymous.
"""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st
from sqlalchemy.orm import Session

from analytics.assessment_analysis import (
    get_assessment_performance,
    list_finalization_readiness,
)
from analytics.corrections import get_correction_analytics
from analytics.data_quality import get_data_quality_report
from analytics.distributions import get_grade_distribution
from analytics.filters import AnalyticsFilter
from analytics.overview import get_admin_overview, get_instructor_overview
from analytics.progress import get_grading_progress
from analytics.question_analysis import list_question_analyses
from analytics.workload import get_instructor_workload, list_all_instructor_workloads
from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory
from models.assessment import Assessment
from models.material import Material
from services.audit_service import (
    ACTION_ANALYTICS_DATA_QUALITY_VIEWED,
    ACTION_ANALYTICS_REPORT_EXPORTED,
    ACTION_ANALYTICS_VIEWED,
    record_audit_event,
)
from services.authorization_service import (
    PERM_EXPORT_ANALYTICS,
    AuthContext,
    can_access_page,
    has_permission,
    require_page_access,
)
from services.logging_service import get_logger
from ui.session import get_current_role, get_current_user_id, get_current_username

_logger = get_logger("analytics_page")

# ── Page configuration ───────────────────────────────────────────

st.set_page_config(
    page_title="Analytics",
    page_icon="📊",
    layout="wide",
)


def _get_role() -> str:
    """Get the current user role from session state."""
    return get_current_role()


def _get_auth_context() -> AuthContext | None:
    """Get the current auth context."""
    role = get_current_role()
    if role == "anonymous":
        return None
    return AuthContext(
        user_id=get_current_user_id() or "",
        username=get_current_username() or "",
        role=role,
    )


def _get_session() -> Session:
    """Get a database session."""
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url())
    factory = create_session_factory(engine)
    return factory()


def _load_materials(session: Session) -> list[tuple[str, str]]:
    """Load materials for filter dropdown."""
    mats = session.query(Material).order_by(Material.name).all()
    return [(m.id, m.name) for m in mats]


def _load_assessments(
    session: Session,
    material_id: str | None = None,
    ctx: AuthContext | None = None,
) -> list[tuple[str, str]]:
    """Load assessments for filter dropdown with auth check."""
    from analytics.filters import authorized_assessment_ids

    auth_ids = authorized_assessment_ids(session, ctx)
    query = session.query(Assessment).filter(Assessment.id.in_(auth_ids))
    if material_id:
        query = query.filter(Assessment.material_id == material_id)
    asmts = query.order_by(Assessment.title).all()
    return [(a.id, a.title) for a in asmts]


def _build_filter_from_sidebar(ctx: AuthContext | None) -> AnalyticsFilter:
    """Build an AnalyticsFilter from sidebar widgets."""
    settings = get_settings()
    f = AnalyticsFilter(
        minimum_group_size=settings.analytics_minimum_group_size,
    )

    session = _get_session()
    try:
        from services.academic_structure_service import (
            list_academic_years as _list_yrs,
        )
        from services.academic_structure_service import (
            list_departments as _list_depts,
        )
        from services.academic_structure_service import (
            list_stages as _list_stgs,
        )
        from services.academic_structure_service import (
            list_terms as _list_trms,
        )

        # Classification filters
        st.sidebar.markdown("### Classification")

        depts = _list_depts(session)
        dept_options = [("", "All Departments")] + [(d.id, d.display_name) for d in depts]
        dept_id = st.sidebar.selectbox(
            "Department",
            options=[d[0] for d in dept_options],
            format_func=lambda x: next((d[1] for d in dept_options if d[0] == x), "All Departments"),
            key="analytics_dept_filter",
        )
        if dept_id:
            f.department_id = dept_id

        stages = _list_stgs(session)
        stage_options = [("", "All Stages")] + [(s.id, s.display_name) for s in stages]
        stage_id = st.sidebar.selectbox(
            "Stage",
            options=[s[0] for s in stage_options],
            format_func=lambda x: next((s[1] for s in stage_options if s[0] == x), "All Stages"),
            key="analytics_stage_filter",
        )
        if stage_id:
            f.academic_stage_id = stage_id

        terms = _list_trms(session)
        term_options = [("", "All Terms")] + [(t.id, t.display_name) for t in terms]
        term_id = st.sidebar.selectbox(
            "Term",
            options=[t[0] for t in term_options],
            format_func=lambda x: next((t[1] for t in term_options if t[0] == x), "All Terms"),
            key="analytics_term_filter",
        )
        if term_id:
            f.academic_term_id = term_id

        years = _list_yrs(session)
        year_options = [("", "All Years")] + [(y.id, y.display_name) for y in years]
        year_id = st.sidebar.selectbox(
            "Academic Year",
            options=[y[0] for y in year_options],
            format_func=lambda x: next((y[1] for y in year_options if y[0] == x), "All Years"),
            key="analytics_year_filter",
        )
        if year_id:
            f.academic_year_id = year_id

        # Material / Assessment filters
        st.sidebar.markdown("### Material & Assessment")
        materials = _load_materials(session)
        # If classification filter is set, narrow materials
        if dept_id or stage_id or term_id or year_id:
            from models.material import Material as MatModel
            mat_query = session.query(MatModel)
            if dept_id:
                mat_query = mat_query.filter(MatModel.department_id == dept_id)
            if stage_id:
                mat_query = mat_query.filter(MatModel.academic_stage_id == stage_id)
            if term_id:
                mat_query = mat_query.filter(MatModel.academic_term_id == term_id)
            if year_id:
                mat_query = mat_query.filter(MatModel.academic_year_id == year_id)
            filtered_mats = [(m.id, m.name) for m in mat_query.all()]
            materials = filtered_mats or materials  # fallback to all if empty
        mat_options = [("", "All Materials")] + materials
        mat_id = st.sidebar.selectbox(
            "Material",
            options=[m[0] for m in mat_options],
            format_func=lambda x: next((m[1] for m in mat_options if m[0] == x), "All Materials"),
            key="analytics_mat_filter",
        )
        if mat_id:
            f.material_id = mat_id

        assessments = _load_assessments(session, mat_id or None, ctx)
        asmt_options = [("", "All Assessments")] + assessments
        asmt_id = st.sidebar.selectbox(
            "Assessment",
            options=[a[0] for a in asmt_options],
            format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "All Assessments"),
            key="analytics_asmt_filter",
        )
        if asmt_id:
            f.assessment_id = asmt_id

        # Date range
        st.sidebar.markdown("### Date Range")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            date_from = st.date_input(
                "From",
                value=None,
                key="analytics_date_from",
            )
        with col2:
            date_to = st.date_input(
                "To",
                value=None,
                key="analytics_date_to",
            )
        if date_from:
            f.date_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=UTC)
        if date_to:
            f.date_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=UTC)

        return f
    finally:
        session.close()


def _log_analytics_view(report_type: str, ctx: AuthContext | None) -> None:
    """Log an analytics view audit event (rate-limited to avoid noise)."""
    if ctx is None:
        return
    session = _get_session()
    try:
        record_audit_event(
            session=session,
            action=ACTION_ANALYTICS_VIEWED,
            user_id=ctx.user_id,
            metadata_json={
                "report_type": report_type,
                "suppression_applied": False,
            },
        )
    except Exception as exc:
        _logger.warning("Audit log failed (analytics view): %s", exc)
    finally:
        session.close()


# ── Tab rendering functions ──────────────────────────────────────


def _render_admin_overview(session: Session, ctx: AuthContext | None) -> None:
    """Render administrator overview tab."""
    st.subheader("📊 Overview Dashboard")

    metrics = get_admin_overview(session, ctx)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Materials", metrics.total_materials)
        st.metric("Active Assessments", metrics.active_assessments)
    with col2:
        st.metric("Total Assessments", metrics.total_assessments)
        st.metric("Finalized", metrics.finalized_assessments)
    with col3:
        st.metric("Total Submissions", metrics.total_submissions)
        st.metric("Grading Completion", f"{metrics.grading_completion_percentage}%")
    with col4:
        st.metric("Avg Turnaround (hrs)", metrics.avg_grading_turnaround_hours or "—")
        st.metric("Active Claims", metrics.active_grading_claims)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pending Grading", metrics.pending_grading)
        st.metric("Drafts", metrics.drafts)
    with col2:
        st.metric("Corrections", metrics.returned_corrections)
        st.metric("Approved", metrics.approved_submissions)
    with col3:
        st.metric("Ready for Finalization", metrics.ready_for_finalization)
        st.metric("Blocked", metrics.blocked_from_finalization)

    st.caption("All counts are aggregate and privacy-safe. No individual student data is shown.")


def _render_instructor_overview(session: Session, ctx: AuthContext | None) -> None:
    """Render instructor overview tab."""
    st.subheader("📊 My Overview")

    metrics = get_instructor_overview(session, ctx)
    if metrics.privacy.suppressed:
        st.info("No analytics data available.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Assigned Assessments", metrics.assigned_assessments)
        st.metric("Pending Submissions", metrics.pending_submissions)
    with col2:
        st.metric("Drafts", metrics.drafts)
        st.metric("Completed Grading", metrics.completed_grading)
    with col3:
        st.metric("Corrections", metrics.returned_corrections)
        st.metric("Active Claims", metrics.active_claims)
    with col4:
        st.metric("Completion %", f"{metrics.completion_percentage}%")
        st.metric("Avg Turnaround (hrs)", metrics.avg_turnaround_hours or "—")


def _render_grading_progress(session: Session, ctx: AuthContext | None, filter_obj: AnalyticsFilter) -> None:
    """Render grading progress tab."""
    st.subheader("📈 Grading Progress")

    progress = get_grading_progress(session, ctx, filter_obj=filter_obj)
    if progress.privacy.suppressed:
        if progress.privacy.reason == "no_authorized_data":
            st.info("No authorized data for the selected filters.")
        else:
            st.warning(f"Data suppressed: group size below privacy threshold ({progress.privacy.minimum_group_size}).")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Submissions", progress.total_submissions)
        st.metric("Not Started", progress.not_started)
    with col2:
        st.metric("Claimed", progress.claimed)
        st.metric("Draft", progress.draft)
    with col3:
        st.metric("Completed", progress.completed)
        st.metric("Needs Correction", progress.needs_correction)
    with col4:
        st.metric("Approved", progress.approved)
        st.metric("Finalized", progress.finalized)

    st.progress(progress.percentage_complete / 100.0, text=f"{progress.percentage_complete}% Complete")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Active Claims", progress.active_claims)
        st.metric("Stale Claims", progress.stale_claims)
    with col2:
        val = progress.avg_claim_to_completion_hours
        st.metric("Avg Claim→Complete (hrs)", val if val is not None else "—")
    with col3:
        val = progress.avg_return_to_correction_hours
        st.metric("Avg Return→Correction (hrs)", val if val is not None else "—")


def _render_workload(session: Session, ctx: AuthContext | None) -> None:
    """Render workload tab (admin sees all, instructor sees own)."""
    is_admin = ctx and ctx.role == "administrator"

    if is_admin:
        st.subheader("👥 Instructor Workload Comparison")
        workloads = list_all_instructor_workloads(session, ctx)
        if not workloads:
            st.info("No instructor workload data available.")
            return

        data = []
        for w in workloads:
            data.append({
                "Instructor": w.instructor_display_name or "—",
                "Assignments": w.active_assignments,
                "Assessments": w.assigned_assessments,
                "Total Subs": w.assigned_submissions,
                "Pending": w.pending_submissions,
                "Completed": w.completed_submissions,
                "Corrections": w.corrections_pending,
                "Completion %": w.completion_percentage,
                "Avg Duration (hrs)": w.avg_grading_duration_hours or "—",
                "Active Claims": w.active_claims,
                "Stale Claims": w.stale_claims,
                "Status": w.workload_status,
            })
        st.dataframe(data, use_container_width=True)
    else:
        st.subheader("👤 My Workload")
        wl = get_instructor_workload(session, ctx, ctx.user_id if ctx else None)
        if wl.privacy.suppressed:
            st.info("No workload data available.")
            return

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Assignments", wl.active_assignments)
            st.metric("Assigned Submissions", wl.assigned_submissions)
        with col2:
            st.metric("Pending", wl.pending_submissions)
            st.metric("Completed", wl.completed_submissions)
        with col3:
            st.metric("Corrections Pending", wl.corrections_pending)
            st.metric("Completion %", f"{wl.completion_percentage}%")
        with col4:
            st.metric("Active Claims", wl.active_claims)
            st.metric("Status", wl.workload_status)


def _render_assessment_performance(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter,
) -> None:
    """Render assessment performance tab."""
    st.subheader("📋 Assessment Performance")

    assessments = _load_assessments(session, filter_obj.material_id, ctx)
    asmt_options = [("", "Select an assessment...")] + assessments
    asmt_id = st.selectbox(
        "Choose Assessment",
        options=[a[0] for a in asmt_options],
        format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "Select an assessment..."),
        key="analytics_perf_asmt",
    )

    if not asmt_id:
        st.info("Select an assessment to view performance metrics.")
        return

    perf = get_assessment_performance(session, ctx, asmt_id, filter_obj)
    if perf.privacy.suppressed:
        st.warning("Data suppressed: group size below privacy threshold.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Submissions", perf.submission_count)
        st.metric("Graded", perf.graded_count)
    with col2:
        st.metric("Mean Grade", perf.mean_grade or "—")
        st.metric("Median Grade", perf.median_grade or "—")
    with col3:
        st.metric("Min Grade", perf.minimum_grade or "—")
        st.metric("Max Grade", perf.maximum_grade or "—")
    with col4:
        st.metric("Std Dev", perf.standard_deviation or "—")
        st.metric("Pass %", f"{perf.pass_percentage}%")

    st.caption(f"Population: {perf.population_mode} submissions | "
               f"Ready for finalization: {'Yes' if perf.ready_for_finalization else 'No'} | "
               f"Blockers: {perf.blocker_count}")


def _render_question_analysis(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter,
) -> None:
    """Render question analysis tab."""
    st.subheader("❓ Question Analysis")

    assessments = _load_assessments(session, filter_obj.material_id, ctx)
    asmt_options = [("", "Select an assessment...")] + assessments
    asmt_id = st.selectbox(
        "Choose Assessment",
        options=[a[0] for a in asmt_options],
        format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "Select..."),
        key="analytics_qa_asmt",
    )

    if not asmt_id:
        st.info("Select an assessment to view question analytics.")
        return

    questions = list_question_analyses(session, ctx, asmt_id, filter_obj)
    if not questions:
        st.info("No question data available.")
        return

    data = []
    for q in questions:
        flags = ", ".join(q.flags) if q.flags else "—"
        data.append({
            "Q#": q.question_number,
            "Max Grade": float(q.maximum_grade),
            "Graded": q.graded_response_count,
            "Mean": q.mean_awarded or "—",
            "Median": q.median_awarded or "—",
            "Avg %": f"{q.average_percentage}%" if q.average_percentage is not None else "—",
            "Difficulty": round(q.difficulty_index, 2) if q.difficulty_index is not None else "—",
            "Full/Zero/Partial": f"{q.full_score_count}/{q.zero_score_count}/{q.partial_credit_count}",
            "Unanswered": q.unanswered_count,
            "Flags": flags,
        })
    st.dataframe(data, use_container_width=True)

    st.caption("Difficulty: 0.0–0.3 = Difficult, 0.3–0.7 = Moderate, 0.7–1.0 = Easy. "
               "Flags are advisory only — not automatic academic judgments.")


def _render_grade_distribution(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter,
) -> None:
    """Render grade distribution tab."""
    st.subheader("📊 Grade Distribution")

    assessments = _load_assessments(session, filter_obj.material_id, ctx)
    asmt_options = [("", "Select an assessment...")] + assessments
    asmt_id = st.selectbox(
        "Choose Assessment",
        options=[a[0] for a in asmt_options],
        format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "Select..."),
        key="analytics_dist_asmt",
    )

    if not asmt_id:
        st.info("Select an assessment to view grade distribution.")
        return

    dist = get_grade_distribution(session, ctx, asmt_id, filter_obj)
    if dist.privacy.suppressed:
        st.warning("Data suppressed: group size below privacy threshold.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Submissions", dist.submission_count)
        st.metric("Mean %", f"{dist.mean_grade_pct}%" if dist.mean_grade_pct is not None else "—")
    with col2:
        st.metric("Pass %", f"{dist.pass_percentage}%")
        st.metric("Median %", f"{dist.median_grade_pct}%" if dist.median_grade_pct is not None else "—")
    with col3:
        st.metric("Q1 %", f"{dist.lower_quartile_pct}%" if dist.lower_quartile_pct is not None else "—")
        st.metric("Q3 %", f"{dist.upper_quartile_pct}%" if dist.upper_quartile_pct is not None else "—")

    # Grade band table
    if dist.bands:
        st.subheader("Grade Bands")
        band_data = []
        for b in dist.bands:
            band_data.append({
                "Band": b.label,
                "Count": b.count,
                "Percentage": f"{b.percentage:.1f}%",
            })
        st.dataframe(band_data, use_container_width=True)

        # Simple bar chart
        chart_data = {b.label: b.count for b in dist.bands}
        st.bar_chart(chart_data)


def _render_corrections(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter,
) -> None:
    """Render correction analytics tab."""
    st.subheader("🔄 Correction Analytics")

    assessments = _load_assessments(session, filter_obj.material_id, ctx)
    asmt_options = [("", "All Assessments")] + assessments
    asmt_id = st.selectbox(
        "Assessment (optional)",
        options=[a[0] for a in asmt_options],
        format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "All Assessments"),
        key="analytics_corr_asmt",
    )

    corr = get_correction_analytics(session, ctx, asmt_id or None, filter_obj)
    if corr.privacy.suppressed:
        st.warning("Data suppressed: group size below privacy threshold.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Returned", corr.total_returned_for_correction)
        st.metric("Resolved", corr.resolved_corrections)
    with col2:
        st.metric("Unresolved", corr.unresolved_corrections)
        st.metric("Completion %", f"{corr.correction_completion_percentage}%")
    with col3:
        st.metric("Avg Cycles", corr.avg_correction_cycles or "—")
        st.metric("Avg Return→Correction (hrs)", corr.avg_return_to_correction_hours or "—")
    with col4:
        st.metric("Assessment Correction Rate", f"{corr.assessment_correction_rate:.1%}")


def _render_finalization_readiness(
    session: Session,
    ctx: AuthContext | None,
    filter_obj: AnalyticsFilter,
) -> None:
    """Render finalization readiness tab."""
    st.subheader("✅ Finalization Readiness")

    items = list_finalization_readiness(session, ctx, filter_obj)
    if not items:
        st.info("No assessments available for finalization readiness review.")
        return

    data = []
    for item in items:
        blockers = ", ".join(item.blocker_reason_codes) if item.blocker_reason_codes else "—"
        data.append({
            "Assessment": item.assessment_title,
            "Total": item.total_submissions,
            "Graded": item.graded,
            "Drafts": item.drafts,
            "Active Claims": item.active_claims,
            "Stale Claims": item.stale_claims,
            "Unresolved Corrections": item.unresolved_corrections,
            "Approvals Pending": item.approvals_pending,
            "Status": item.readiness_status,
            "Blockers": blockers,
        })
    st.dataframe(data, use_container_width=True)


def _render_data_quality(session: Session, ctx: AuthContext | None) -> None:
    """Render data quality report tab (admin only)."""
    st.subheader("🔍 Data Quality Report")

    report = get_data_quality_report(session, ctx)
    if not report.issues:
        st.success("No data quality issues found.")
        return

    st.metric("Total Issues", report.total_issues)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔴 Critical", report.critical_count)
    with col2:
        st.metric("🟡 Warning", report.warning_count)
    with col3:
        st.metric("🔵 Info", report.info_count)

    data = []
    for issue in report.issues:
        severity_icon = {"critical": "🔴", "warning": "🟡", "information": "🔵"}.get(issue.severity, "⚪")
        data.append({
            "Severity": f"{severity_icon} {issue.severity}",
            "Type": issue.issue_type,
            "Count": issue.count,
            "Description": issue.description,
        })
    st.dataframe(data, use_container_width=True)

    # Log audit event
    try:
        record_audit_event(
            session=session,
            action=ACTION_ANALYTICS_DATA_QUALITY_VIEWED,
            user_id=ctx.user_id if ctx else "",
            metadata_json={"issue_count": report.total_issues},
        )
    except Exception as exc:
        _logger.warning("Audit log failed (data quality view): %s", exc)


def _render_export(session: Session, ctx: AuthContext | None, filter_obj: AnalyticsFilter) -> None:
    """Render export tab."""
    st.subheader("📤 Export Reports")

    get_settings()
    can_export = has_permission(ctx.role if ctx else "", PERM_EXPORT_ANALYTICS) if ctx else False
    if not can_export:
        st.info("Analytics export is not enabled for your role.")
        return

    assessments = _load_assessments(session, filter_obj.material_id, ctx)
    asmt_options = [("", "Select an assessment...")] + assessments
    asmt_id = st.selectbox(
        "Choose Assessment for Report",
        options=[a[0] for a in asmt_options],
        format_func=lambda x: next((a[1] for a in asmt_options if a[0] == x), "Select..."),
        key="analytics_export_asmt",
    )

    if not asmt_id:
        st.info("Select an assessment and click Export to generate a report.")
        return

    if st.button("📥 Export Assessment Summary (XLSX)", type="primary"):
        try:
            from analytics.export import export_assessment_summary_report

            wb_bytes = export_assessment_summary_report(session, ctx, asmt_id, filter_obj)
            st.download_button(
                label="📥 Download Report",
                data=wb_bytes,
                file_name=f"assessment_summary_{asmt_id[:8]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            # Log export event
            try:
                record_audit_event(
                    session=session,
                    action=ACTION_ANALYTICS_REPORT_EXPORTED,
                    user_id=ctx.user_id if ctx else "",
                    metadata_json={
                        "report_type": "assessment_summary",
                        "assessment_id": asmt_id,
                        "export_format": "xlsx",
                    },
                )
            except Exception as exc:
                _logger.warning("Audit log failed (export): %s", exc)

            st.success("Report generated successfully!")

        except PermissionError:
            st.error("You are not authorized to export this report.")
        except Exception as exc:
            st.error(f"Report generation failed: {exc}")


# ── Main page ────────────────────────────────────────────────────


def main() -> None:
    """Render the Analytics page."""
    ctx = _get_auth_context()
    role = _get_role()

    # Page access check
    if not can_access_page(role, "Analytics"):
        require_page_access(role, "Analytics")
        return

    session = _get_session()
    try:
        st.title("📊 Analytics")
        is_admin = role == "administrator"

        # Sidebar filters
        st.sidebar.header("Analytics Filters")
        filter_obj = _build_filter_from_sidebar(ctx)
        if not filter_obj.is_empty():
            _log_analytics_view(filter_obj.summary(), ctx)

        # Role-aware tabs
        if is_admin:
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
                "Overview", "Grading Progress", "Instructor Workload",
                "Assessment Performance", "Question Analysis",
                "Grade Distribution", "Corrections", "Finalization Readiness",
                "Data Quality", "Export Reports",
            ])
        else:
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "My Overview", "My Progress", "My Workload",
                "Assessment Performance", "Question Analysis",
                "Corrections",
            ])

        if is_admin:
            with tab1:
                _render_admin_overview(session, ctx)
            with tab2:
                _render_grading_progress(session, ctx, filter_obj)
            with tab3:
                _render_workload(session, ctx)
            with tab4:
                _render_assessment_performance(session, ctx, filter_obj)
            with tab5:
                _render_question_analysis(session, ctx, filter_obj)
            with tab6:
                _render_grade_distribution(session, ctx, filter_obj)
            with tab7:
                _render_corrections(session, ctx, filter_obj)
            with tab8:
                _render_finalization_readiness(session, ctx, filter_obj)
            with tab9:
                _render_data_quality(session, ctx)
            with tab10:
                _render_export(session, ctx, filter_obj)
        else:
            with tab1:
                _render_instructor_overview(session, ctx)
            with tab2:
                _render_grading_progress(session, ctx, filter_obj)
            with tab3:
                _render_workload(session, ctx)
            with tab4:
                _render_assessment_performance(session, ctx, filter_obj)
            with tab5:
                _render_question_analysis(session, ctx, filter_obj)
            with tab6:
                _render_corrections(session, ctx, filter_obj)

        st.sidebar.divider()
        st.sidebar.caption(
            "Analytics are descriptive and advisory only. "
            "Data may be suppressed where group sizes fall below privacy thresholds. "
            "No student identity is available in analytics."
        )

    finally:
        session.close()


if __name__ == "__main__":
    main()
