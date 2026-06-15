"""Phase 3/4 import preview page — full workflow with secure import."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from parsers import (
    ColumnClassification,
    ParsedColumn,
    ParsedValidationMessage,
)
from parsers.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    ImportParserError,
    InvalidHtmlError,
    MissingIdentityColumnsError,
    MissingResponseColumnsError,
    MultipleCandidateTablesError,
    NoResponseTableFoundError,
    NoTableFoundError,
    UnsupportedFileTypeError,
)
from parsers.models import ParsedImport
from services.assessment_service import list_assessments
from services.identity_matching_service import get_blocking_rows
from services.import_preview_service import (
    format_file_size,
    preview_html_import,
    reconcile_assessment,
    validate_mapping,
)
from services.logging_service import get_logger
from services.material_service import list_materials
from services.secure_import_service import (
    SecureImportResult,
    compute_dry_run,
    execute_secure_import,
)
from ui.layout import configure_page, render_app_header, render_safe_error

logger = get_logger("import_page")

# ── mapping options shared across columns ──────────────────────────
_MAPPING_OPTIONS = [
    "First name",
    "Last name",
    "Email",
    "Institutional student ID",
    "Status",
    "Started",
    "Completed",
    "Duration",
    "Source grade",
    "Ignore",
    "Unknown",
]

_FIELD_TO_OPTION: dict[str, str] = {
    "first_name": "First name",
    "last_name": "Last name",
    "email": "Email",
    "institutional_student_id": "Institutional student ID",
    "status": "Status",
    "started": "Started",
    "completed": "Completed",
    "duration": "Duration",
    "source_grade": "Source grade",
}


def _option_to_field(option: str) -> str | None:
    mapping = {v: k for k, v in _FIELD_TO_OPTION.items()}
    return mapping.get(option)


def _response_options(max_num: int) -> list[str]:
    return [f"Response question {n}" for n in range(1, max_num + 1)] + ["Ignore", "Unknown"]


# ── helpers ────────────────────────────────────────────────────────


def _show_messages(messages: tuple[ParsedValidationMessage, ...] | list[ParsedValidationMessage]) -> None:
    for message in messages:
        prefix = f"[{message.code}] " if message.code else ""
        severity = message.severity.value if hasattr(message.severity, "value") else "information"
        if severity == "error":
            st.error(prefix + message.message)
        elif severity == "warning":
            st.warning(prefix + message.message)
        else:
            st.info(prefix + message.message)


def _build_mapping_from_ui(columns: tuple[ParsedColumn, ...], responses_needed: int) -> dict[int, str]:
    """Read widget values from session state and build column-index → mapped-field dict."""
    mapping: dict[int, str] = {}
    for col in columns:
        key = f"map_{col.index}"
        val = st.session_state.get(key, "")
        if val and val not in ("Unknown", "Ignore"):
            if val.startswith("Response question "):
                mapping[col.index] = f"response_{val.split()[-1]}"
            elif val == "Source grade":
                mapping[col.index] = "source_grade"
            else:
                mapped = _option_to_field(val)
                if mapped:
                    mapping[col.index] = mapped
    return mapping


def _apply_mapping(parsed: ParsedImport, mapping: dict[int, str]) -> ParsedImport:
    """Rebuild ParsedImport columns with user-specified mapping."""
    new_columns: list[ParsedColumn] = []
    for col in parsed.columns:
        mapped = mapping.get(col.index)
        if mapped is None:
            if col.classification is ColumnClassification.RESPONSE:
                mapped = f"response_{col.response_number}" if col.response_number else "unknown"
            else:
                mapped = col.mapped_field or "unknown"
        classification = ColumnClassification.UNKNOWN
        response_number: int | None = None
        if mapped == "ignore":
            classification = ColumnClassification.IGNORED
            mapped = None
        elif mapped in ("first_name", "last_name", "email", "institutional_student_id"):
            classification = ColumnClassification.IDENTITY
        elif mapped in ("status", "started", "completed", "duration", "source_grade"):
            classification = ColumnClassification.METADATA
        elif mapped and mapped.startswith("response_"):
            classification = ColumnClassification.RESPONSE
            try:
                response_number = int(mapped.split("_")[1])
            except (IndexError, ValueError):
                pass
        new_columns.append(
            ParsedColumn(
                original_name=col.original_name,
                normalized_name=col.normalized_name,
                index=col.index,
                classification=classification,
                mapped_field=mapped,
                is_required=col.is_required,
                confidence=0.5 if mapped != col.mapped_field else col.confidence,
                warnings=(),
                response_number=response_number,
            )
        )
    return ParsedImport(
        source_filename=parsed.source_filename,
        parser_name=parsed.parser_name,
        table_index=parsed.table_index,
        columns=tuple(new_columns),
        rows=parsed.rows,
        response_columns=tuple(c for c in new_columns if c.classification is ColumnClassification.RESPONSE),
        unknown_columns=tuple(c for c in new_columns if c.classification is ColumnClassification.UNKNOWN),
        warnings=parsed.warnings,
        errors=parsed.errors,
        statistics=parsed.statistics,
        parse_started_at=parsed.parse_started_at,
        parse_completed_at=parsed.parse_completed_at,
        candidate_tables=parsed.candidate_tables,
    )


def _render_stats(preview_result: Any) -> None:
    s = preview_result.parsed_import.statistics
    cols = st.columns(5)
    cols[0].metric("Rows", s.total_rows)
    cols[1].metric("Valid", s.valid_rows)
    cols[2].metric("Warnings", s.warning_rows)
    cols[3].metric("Errors", s.error_rows)
    cols[4].metric("Response columns", s.response_column_count)
    cols2 = st.columns(4)
    cols2[0].metric("Blank responses", s.blank_response_count)
    cols2[1].metric("Duplicate emails", s.duplicate_email_count)
    cols2[2].metric("Duplicate IDs", s.duplicate_student_id_count)
    cols2[3].metric("Unknown columns", s.unknown_column_count)


def _render_mapping_editor(preview_result: Any, responses_needed: int) -> dict[int, str]:
    """Render editable column mapping and return the current mapping."""
    st.markdown("### Column Mapping")
    st.caption("Adjust how each column is interpreted.")
    resp_opts = _response_options(max(responses_needed, 5))
    data: list[dict[str, Any]] = []
    for col in preview_result.parsed_import.columns:
        default = "Unknown"
        if col.classification is ColumnClassification.IDENTITY and col.mapped_field:
            default = _FIELD_TO_OPTION.get(col.mapped_field, "Unknown")
        elif col.classification is ColumnClassification.METADATA and col.mapped_field:
            default = _FIELD_TO_OPTION.get(col.mapped_field, "Source grade")
        elif col.classification is ColumnClassification.RESPONSE:
            default = f"Response question {col.response_number}" if col.response_number else "Unknown"
        data.append({
            "Original": col.original_name,
            "Normalized": col.normalized_name,
            "Suggestion": default,
            "Confidence": f"{col.confidence:.0%}",
            "Key": f"map_{col.index}",
            "Options": (
                resp_opts
                if col.classification in (ColumnClassification.RESPONSE, ColumnClassification.UNKNOWN)
                else _MAPPING_OPTIONS
            ),
        })
    for d in data:
        c1, c2, c3, c4 = st.columns([2, 2, 1, 3])
        c1.write(d["Original"])
        c2.write(d["Normalized"])
        c3.write(d["Confidence"])
        opts = d["Options"]
        idx = opts.index(d["Suggestion"]) if d["Suggestion"] in opts else 0
        c4.selectbox("", opts, index=idx, key=d["Key"], label_visibility="collapsed")
    return _build_mapping_from_ui(preview_result.parsed_import.columns, responses_needed)


def _render_preview(preview_result: Any) -> None:
    """Render a per-row preview table with expandable details."""
    st.markdown("### Preview Rows")
    max_rows = st.selectbox("Rows to show", [10, 20, 50, 100], index=1)
    display_rows = preview_result.parsed_import.rows[:max_rows]
    summary: list[dict[str, Any]] = []
    for row in display_rows:
        summary.append({
            "Row": row.row_number,
            "First name": row.first_name or "",
            "Last name": row.last_name or "",
            "Email": row.email or "",
            "Student ID": row.institutional_student_id or "",
            "Status": row.status or "",
            "Responses": len(row.responses),
            "Blank": sum(1 for r in row.responses if r.is_blank),
            "Warnings": len(row.warnings),
            "Errors": len(row.errors),
        })
    st.dataframe(summary, use_container_width=True, hide_index=True)
    for row in display_rows:
        with st.expander(f"Row {row.row_number} — {row.first_name or ''} {row.last_name or ''}".strip()):
            if row.status:
                st.write(f"**Status:** {row.status}")
            if row.started:
                st.write(f"**Started:** {row.started}")
            if row.completed:
                st.write(f"**Completed:** {row.completed}")
            if row.duration_seconds is not None:
                st.write(f"**Duration:** {row.duration_seconds}s")
            if row.source_grade is not None or row.raw_source_grade:
                st.write(f"**Source grade (informational):** {row.raw_source_grade or ''}")
            for resp in row.responses:
                st.markdown(f"**Response {resp.question_number}**")
                if resp.is_blank:
                    st.caption("*(blank)*")
                else:
                    st.code(resp.text, language="text")
            if row.unknown_values:
                st.write("**Unknown values:**", row.unknown_values)
            _show_messages(row.warnings)
            _show_messages(row.errors)


# ── main ───────────────────────────────────────────────────────────


def main() -> None:
    configure_page("Import")
    render_app_header()
    st.subheader("📥 HTML Import")
    st.caption("Phase 3: Preview & Mapping  |  Phase 4: Secure Import with Encryption")

    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    factory = create_session_factory(engine)

    # Step 1 — Select material
    with session_scope(factory) as session:
        materials = list_materials(session, include_archived=False)
    mat_options = {m.name: m.id for m in materials} if materials else {}
    if not mat_options:
        st.info("No active materials found. Create a material first on the Materials page.")
        return
    selected_material_name = st.selectbox("1. Select Material", list(mat_options.keys()))
    material_id = mat_options[selected_material_name]

    # Step 2 — Select assessment
    with session_scope(factory) as session:
        assessments = list_assessments(session, material_id, status_filter=None)
    draft_asses = [a for a in assessments if a.status in ("draft", "ready")]
    if not draft_asses:
        st.info("No draft or ready assessments found for this material.")
        return
    ass_options = {f"{a.title} ({a.status})": a for a in draft_asses}
    selected_ass_label = st.selectbox("2. Select Assessment", list(ass_options.keys()))
    assessment = ass_options[selected_ass_label]

    # Step 3 — Show assessment details + question info
    with session_scope(factory) as session:
        from services.question_service import list_questions
        questions = list_questions(session, assessment.id)
    st.markdown(
        f"**Assessment:** {assessment.title}  |  "
        f"**Max grade:** {assessment.maximum_grade}  |  "
        f"**Questions:** {len(questions)}"
    )
    q_numbers = tuple(q.question_number for q in questions) if questions else ()
    if q_numbers:
        st.write(f"**Question numbers:** {', '.join(str(n) for n in q_numbers)}")
    responses_needed = max(len(questions), 2)

    # Step 4 — Upload file
    uploaded_file = st.file_uploader("3. Upload HTML response export", type=["html", "htm"])
    if uploaded_file is None:
        st.info("Upload a sanitized HTML fixture to preview the parsed columns and rows.")
        return

    file_bytes = uploaded_file.getvalue()
    file_hash = sha256(file_bytes).hexdigest()
    cached = st.session_state.get("_cached_file_hash")
    st.metric("File size", format_file_size(len(file_bytes)))

    # Step 5 — Parse
    try:
        if cached != file_hash:
            preview = preview_html_import(file_bytes, uploaded_file.name)
            st.session_state["_preview"] = preview
            st.session_state["_cached_file_hash"] = file_hash
            st.session_state["_selected_table"] = None
        else:
            preview = st.session_state.get("_preview")  # type: ignore[assignment]
            if preview is None:
                preview = preview_html_import(file_bytes, uploaded_file.name)
                st.session_state["_preview"] = preview
                st.session_state["_cached_file_hash"] = file_hash
    except (
        EmptyFileError, FileTooLargeError, InvalidHtmlError,
        NoTableFoundError, NoResponseTableFoundError,
        MultipleCandidateTablesError, MissingIdentityColumnsError,
        MissingResponseColumnsError, UnsupportedFileTypeError,
    ) as exc:
        render_safe_error(str(exc))
        return
    except ImportParserError as exc:
        render_safe_error(str(exc))
        return

    # Step 6 — Table selection
    candidates = preview.parsed_import.candidate_tables
    if len(candidates) > 1:
        st.markdown("### Candidate Tables")
        opts = {
            f"Table {c.index + 1}: {c.row_count} rows, "
            f"{c.response_columns} responses, score={c.score}": c.index
            for c in candidates
        }
        sel_label = st.selectbox("4. Select Table", list(opts.keys()))
        sel_index = opts[sel_label]
        if st.session_state.get("_selected_table") != sel_index:
            preview = preview_html_import(file_bytes, uploaded_file.name, table_index=sel_index)
            st.session_state["_preview"] = preview
            st.session_state["_selected_table"] = sel_index
    elif candidates:
        cand = candidates[0]
        st.caption(
            f"Auto-selected table {cand.index + 1} "
            f"({cand.row_count} rows, {cand.response_columns} responses)"
        )

    st.markdown("### File Statistics")
    _render_stats(preview)

    # Step 7 — Column mapping
    st.markdown("### Column Mapping")
    mapping = _render_mapping_editor(preview, responses_needed)

    # Step 8 — Apply mapping + revalidate
    adjusted = _apply_mapping(preview.parsed_import, mapping)
    mapping_valid = validate_mapping(adjusted)
    reconciliation = reconcile_assessment(adjusted, q_numbers)

    _show_messages(mapping_valid.messages)

    if reconciliation.exact_match:
        st.success(f"✅ {reconciliation.message}")
    elif reconciliation.unresolved:
        st.warning(f"⚠️ {reconciliation.message}")
    else:
        st.info(reconciliation.message)

    # Step 9 — Preview
    _render_preview(preview)

    # Step 10 — Source-grade disclaimer
    st.caption(
        "Source grades from the import file are informational. "
        "They are not automatically accepted as final grades."
    )

    # Step 11 — Validation messages
    _show_messages(preview.parsed_import.warnings)
    _show_messages(preview.parsed_import.errors)

    # Step 12 — Phase 3 Readiness
    ready = (
        mapping_valid.valid
        and reconciliation.exact_match
        and not preview.parsed_import.errors
        and all(not row.errors for row in preview.parsed_import.rows)
    )
    if ready:
        st.success("✅ **Phase 3 Validation Complete.**")
    else:
        reasons = []
        if not mapping_valid.valid:
            reasons.append("Column mapping has unresolved errors")
        if not reconciliation.exact_match:
            reasons.append("Assessment reconciliation is incomplete")
        if preview.parsed_import.errors:
            reasons.append("File-level validation errors exist")
        if any(row.errors for row in preview.parsed_import.rows):
            reasons.append("Row-level validation errors exist")
        st.warning(f"⚠️ **Not Ready.** {'; '.join(reasons)}.")
        logger.info(
            "Import preview — %s, %s rows, ready=%s",
            uploaded_file.name,
            preview.parsed_import.statistics.total_rows,
            ready,
        )
        return

    st.markdown("---")
    st.subheader("🔐 Phase 4 — Secure Anonymous Import")

    # ── Phase 4 requires a database session ──
    # We already have settings, engine, factory

    # Step 11 — Identity matching dry run
    st.markdown("### Step 11 — Identity Matching Dry Run")
    with st.spinner("Running identity matching dry run..."):
        with session_scope(factory) as session:
            adjusted_parsed = _apply_mapping(preview.parsed_import, mapping)
            dry_run = compute_dry_run(
                parsed=adjusted_parsed,
                session=session,
                assessment_id=assessment.id,
                file_hash=file_hash,
            )

    if not dry_run.keys_available:
        st.warning(
            "⚠️ **Encryption and fingerprint keys are not configured.**\n\n"
            "Set `IDENTITY_ENCRYPTION_KEY` and `IDENTITY_FINGERPRINT_KEY` "
            "in your `.env` file to enable secure import. "
            "Phase 3 preview and mapping will continue to work without these keys."
        )
        st.info(
            f"**Dry run summary (keys unavailable):** "
            f"{dry_run.rows_ready} rows ready, "
            f"{dry_run.new_identities} would create new identities, "
            f"{dry_run.manual_resolution} require manual resolution, "
            f"{dry_run.skipped_rows} skipped."
        )
        # Don't proceed further without keys
        return

    # Display dry run summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows ready", dry_run.rows_ready)
    col2.metric("Matched by ID", dry_run.matched_by_id)
    col3.metric("Matched by Email", dry_run.matched_by_email)
    col4.metric("New identities", dry_run.new_identities)

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Ambiguous", dry_run.ambiguous)
    col6.metric("Manual resolution", dry_run.manual_resolution)
    col7.metric("Skipped rows", dry_run.skipped_rows)
    col8.metric("Duplicate file", "⚠️ Yes" if dry_run.duplicate_file else "No")

    st.caption(
        f"Expected: {dry_run.expected_submissions} submissions, "
        f"{dry_run.expected_responses} responses"
    )

    if dry_run.duplicate_file:
        st.error(
            "🚫 **This file has already been imported for this assessment.** "
            "Duplicate imports are blocked."
        )
        logger.info(
            "Duplicate file blocked — %s, hash=%s",
            uploaded_file.name, file_hash[:16],
        )
        return

    # Step 12 — Manual identity resolution
    blocking_rows: list[dict[str, object]] = []
    if dry_run.ambiguous > 0 or dry_run.manual_resolution > 0:
        st.markdown("### Step 12 — Manual Identity Resolution")

        with session_scope(factory) as session:
            adjusted_parsed = _apply_mapping(preview.parsed_import, mapping)
            from security.key_validation import load_keys
            try:
                _, fp_key = load_keys(
                    settings.identity_encryption_key,
                    settings.identity_fingerprint_key,
                )
            except Exception:
                fp_key = None

            if fp_key is not None:
                blocking_rows = get_blocking_rows(
                    session, adjusted_parsed.rows, fp_key
                )

        if not blocking_rows:
            st.success("No blocking rows found — all identities resolved automatically.")

        manual_decisions: dict[str, str] = {}
        for br in blocking_rows:
            with st.expander(
                f"Row {br['row_number']} — {br['first_name']} {br['last_name']}",
                expanded=True,
            ):
                st.write(f"**Conflict:** {br['conflict_reason']}")
                st.write(
                    f"Email: {br['email'] or '(none)'}  |  "
                    f"Student ID: {br['institutional_student_id'] or '(none)'}"
                )

                # Get existing identities that might match (by email or ID)
                match_options = ["(Select action...)", "Skip this row", "Create new identity"]
                with session_scope(factory) as session:
                    adjusted_parsed2 = _apply_mapping(preview.parsed_import, mapping)
                    # Find matching row in parsed data to get identity info
                    matching_rows = [r for r in adjusted_parsed2.rows if r.row_number == br["row_number"]]
                    if matching_rows:
                        row_data = matching_rows[0]
                        # Look for potential existing matches
                        from security.fingerprint import (
                            fingerprint_email,
                            fingerprint_institutional_id,
                        )
                        if fp_key is not None:
                            email_fp = fingerprint_email(row_data.email, fp_key) if row_data.email else None
                            id_fp = (
                                fingerprint_institutional_id(
                                    row_data.institutional_student_id, fp_key
                                ) if row_data.institutional_student_id else None
                            )
                        else:
                            email_fp = None
                            id_fp = None

                        from models.student_identity import StudentIdentity
                        ident_candidates: list[StudentIdentity] = []
                        if email_fp:
                            ident_candidates.extend(
                                session.query(StudentIdentity)
                                .filter(StudentIdentity.email_fingerprint == email_fp)
                                .all()
                            )
                        if id_fp:
                            ident_candidates.extend(
                                session.query(StudentIdentity)
                                .filter(StudentIdentity.institutional_id_fingerprint == id_fp)
                                .all()
                            )
                        # Deduplicate
                        seen_ids: set[str] = set()
                        unique_candidates: list[StudentIdentity] = []
                        for c in ident_candidates:
                            if c.id not in seen_ids:
                                seen_ids.add(c.id)
                                unique_candidates.append(c)

                        if unique_candidates:
                            match_options.append("---")
                            for c_id in unique_candidates:
                                match_options.append(f"match:{c_id.id}")

                decision_key = f"manual_{br['row_ref']}"
                decision = st.radio(
                    "Choose action",
                    match_options,
                    key=decision_key,
                    index=0,
                )
                if decision and not decision.startswith("("):
                    row_ref: str = str(br["row_ref"])
                    manual_decisions[row_ref] = decision
                st.session_state["_manual_decisions"] = manual_decisions
    else:
        st.success("✅ No manual resolution required — all identities resolved automatically.")
        st.session_state["_manual_decisions"] = {}

    # Step 13 — Secure import confirmation
    st.markdown("### Step 13 — Secure Import Confirmation")

    # Check if manual decisions are complete
    unresolved_blocking = [
        br for br in blocking_rows
        if br["row_ref"] not in st.session_state.get("_manual_decisions", {})
    ]
    all_resolved = len(unresolved_blocking) == 0

    if not all_resolved:
        remaining = len(unresolved_blocking)
        st.warning(
            f"⚠️ **{remaining} row(s) still require manual resolution.** "
            "Please resolve all ambiguous or missing-identity rows above."
        )

    confirmation_key = "phase4_confirmation"
    confirmed = st.checkbox(
        "I confirm that the column mapping and identity resolutions are correct.",
        key=confirmation_key,
        disabled=not all_resolved,
    )

    can_import = (
        ready
        and dry_run.keys_available
        and not dry_run.duplicate_file
        and all_resolved
        and confirmed
    )

    if st.button(
        "Securely Import Anonymous Submissions",
        type="primary",
        disabled=not can_import,
        use_container_width=True,
    ):
        # Step 14 — Execute secure import
        with st.spinner("Importing submissions securely..."):
            try:
                with session_scope(factory) as session:
                    final_parsed = _apply_mapping(preview.parsed_import, mapping)
                    manual_decisions_final = st.session_state.get("_manual_decisions", {})
                    result: SecureImportResult = execute_secure_import(
                        session=session,
                        parsed=final_parsed,
                        assessment_id=assessment.id,
                        assessment_question_numbers=q_numbers,
                        file_bytes=file_bytes,
                        source_filename=uploaded_file.name,
                        table_index=preview.parsed_import.table_index,
                        manual_decisions=manual_decisions_final,
                    )

                st.markdown("---")
                st.markdown("### ✅ Step 14 — Import Successful")

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Batch Reference", result.import_batch_id[:8])
                col_b.metric("Status", result.status.capitalize())
                col_c.metric("Warnings", result.warning_count)

                col_d, col_e, col_f = st.columns(3)
                col_d.metric("Imported Students", result.imported_student_count)
                col_e.metric("Matched Identities", result.matched_identity_count)
                col_f.metric("New Identities", result.new_identity_count)

                col_g, col_h, col_i = st.columns(3)
                col_g.metric("Submissions", result.submission_count)
                col_h.metric("Responses", result.response_count)
                col_i.metric("Skipped Rows", result.skipped_row_count)

                st.success(
                    "✅ **Import complete.** All student identities are encrypted at rest. "
                    "Anonymous grading codes have been assigned."
                )
                st.caption(
                    "You can now proceed to the Grading page to score responses anonymously."
                )

                logger.info(
                    "Secure import complete — batch=%s, imported=%s, matched=%s, "
                    "new_ids=%s, subs=%s, responses=%s, skipped=%s, warnings=%s",
                    result.import_batch_id[:8],
                    result.imported_student_count,
                    result.matched_identity_count,
                    result.new_identity_count,
                    result.submission_count,
                    result.response_count,
                    result.skipped_row_count,
                    result.warning_count,
                )

            except ValueError as exc:
                render_safe_error(str(exc))
                logger.error("Secure import failed — %s", str(exc))
            except Exception as exc:
                render_safe_error(f"Import failed: {type(exc).__name__}")
                logger.error("Secure import exception — %s", type(exc).__name__)

    elif confirmed and all_resolved and dry_run.keys_available and not dry_run.duplicate_file:
        st.info("Click the button above to begin the secure import.")

    logger.info(
        "Import preview — %s, %s rows, ready=%s",
        uploaded_file.name,
        preview.parsed_import.statistics.total_rows,
        ready,
    )


if __name__ == "__main__":
    main()
