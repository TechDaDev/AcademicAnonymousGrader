# Academic Anonymous Grader — Backup and Restore Page
"""Administrator-only backup creation and restore."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.audit_service import (
    ACTION_BACKUP_CREATED,
    ACTION_RESTORE_COMPLETED,
    ACTION_RESTORE_FAILED,
    ACTION_RESTORE_STARTED,
    record_audit_event,
)
from services.backup_service import (
    create_backup,
    get_backup_records,
    inspect_backup,
    restore_backup,
    validate_backup_manifest,
    verify_backup_hashes,
)
from services.exceptions import (
    BackupCorruptedError,
    BackupHashMismatchError,
    BackupSchemaMismatchError,
    RestoreFailedError,
    RestoreValidationError,
)
from services.logging_service import get_logger
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import render_logout_button, require_authentication, require_page_access_safe

logger = get_logger("backup_page")

_RESTORE_PHRASE = "RESTORE DATABASE"


def _get_engine_and_factory() -> tuple[Any, Any]:  # noqa: ANN401
    settings = get_settings()
    database_url = settings.resolved_database_url()
    engine = get_engine(database_url, echo=settings.app_debug)
    initialize_database(engine)
    factory = create_session_factory(engine)
    return engine, factory


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _render_database_status() -> None:
    """Show current database status."""
    settings = get_settings()
    database_url = settings.resolved_database_url()
    st.caption(f"Database URL: `{database_url}`")

    from pathlib import Path

    # Parse the database path
    if database_url.startswith("sqlite:///"):
        rel = database_url[len("sqlite:///"):]
        db_path = Path(rel)
        if db_path.exists():
            size = _format_size(db_path.stat().st_size)
            st.caption(f"File size: {size}")
            st.caption(
                "Last modified: "
                f"{datetime.fromtimestamp(db_path.stat().st_mtime, tz=UTC).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            st.caption("Database file not found on disk.")


def _render_create_backup(engine: Any, factory: Any) -> None:  # noqa: ANN401
    """Render the create backup section."""
    st.subheader("💾 Create Backup")

    settings = get_settings()
    database_url = settings.resolved_database_url()
    db_path = None
    if database_url.startswith("sqlite:///"):
        from pathlib import Path

        rel = database_url[len("sqlite:///"):]
        candidate = Path(rel)
        if candidate.exists():
            db_path = candidate

    if db_path is None:
        st.warning("Backup is only supported for SQLite databases.")
        return

    if st.button("📦 Create Backup Now", use_container_width=True, type="primary"):
        try:
            with session_scope(factory) as session:
                zip_bytes, manifest = create_backup(
                    session,
                    engine,
                    db_path,
                    user_id=st.session_state.get("user_id"),
                )
                record_audit_event(
                    session,
                    action=ACTION_BACKUP_CREATED,
                    user_id=st.session_state.get("user_id"),
                    username_snapshot=st.session_state.get("username"),
                    entity_type="backup",
                    entity_id=manifest.get("backup_reference"),
                    outcome="success",
                    metadata_json={
                        "backup_reference": manifest.get("backup_reference"),
                        "file_size": len(zip_bytes),
                    },
                )

            st.success(f"Backup **{manifest['backup_reference']}** created successfully!")
            st.download_button(
                label="⬇️ Download Backup ZIP",
                data=zip_bytes,
                file_name=f"{manifest['backup_reference']}.zip",
                mime="application/zip",
                use_container_width=True,
            )
        except Exception as exc:
            logger.exception("Backup failed")
            render_safe_error(f"Backup failed: {exc}")


def _render_backup_history(factory: Any) -> None:  # noqa: ANN401
    """Render backup history."""
    st.subheader("📋 Backup History")

    try:
        with session_scope(factory) as session:
            records = get_backup_records(session)

        if not records:
            st.info("No backups have been created yet.")
            return

        for rec in records:
            with st.container(border=True):
                cols = st.columns([2, 1, 1, 1])
                with cols[0]:
                    st.markdown(f"**{rec['backup_reference']}**")
                    if rec["created_at"]:
                        st.caption(rec["created_at"].strftime("%Y-%m-%d %H:%M:%S"))
                with cols[1]:
                    st.caption(f"Size: {_format_size(rec['file_size'])}")
                with cols[2]:
                    st.caption(f"Hash: `{rec['file_hash'][:12]}...`")
                with cols[3]:
                    st.caption(f"Status: `{rec['status']}`")
    except Exception:
        logger.exception("Failed to load backup history")
        render_safe_error("Could not load backup history.")


def _render_restore(engine: Any, factory: Any) -> None:  # noqa: ANN401
    """Render the restore section."""
    st.divider()
    st.subheader("⚠️ Restore from Backup")
    st.warning(
        "Restore will replace the current database with the backup version. "
        "A pre-restore backup will be created automatically before restoring."
    )

    uploaded_file = st.file_uploader(
        "Upload Backup ZIP",
        type=["zip"],
        key="restore_upload",
    )

    if uploaded_file is not None:
        backup_bytes = uploaded_file.getvalue()

        # Inspect manifest
        try:
            manifest = inspect_backup(backup_bytes)
            validate_backup_manifest(manifest)
            verify_backup_hashes(backup_bytes, manifest)

            st.success("✅ Backup verified — manifest valid, hashes match.")

            with st.container(border=True):
                st.markdown(f"**Reference:** {manifest.get('backup_reference', 'N/A')}")
                st.markdown(f"**Created:** {manifest.get('created_at', 'N/A')}")
                st.markdown(f"**App Version:** {manifest.get('app_version', 'N/A')}")
                st.markdown(f"**Schema Version:** {manifest.get('schema_version', 'N/A')}")
                tables = manifest.get("tables", [])
                st.markdown(f"**Tables ({len(tables)}):** {', '.join(tables)}")

            st.divider()

            # Confirmation phrase
            st.markdown("#### Confirm Restore")
            st.caption(
                f"Type `{_RESTORE_PHRASE}` exactly to confirm you want to restore "
                "this backup."
            )
            confirmation = st.text_input(
                "Confirmation phrase",
                placeholder=_RESTORE_PHRASE,
                key="restore_confirm",
            )

            db_path = None
            settings = get_settings()
            database_url = settings.resolved_database_url()
            if database_url.startswith("sqlite:///"):
                from pathlib import Path

                rel = database_url[len("sqlite:///"):]
                candidate = Path(rel)
                if candidate.exists():
                    db_path = candidate

            if confirmation == _RESTORE_PHRASE and db_path is not None:
                if st.button(
                    "🔄 Restore Database",
                    type="primary",
                    use_container_width=True,
                    key="restore_button",
                ):
                    try:
                        with session_scope(factory) as session:
                            record_audit_event(
                                session,
                                action=ACTION_RESTORE_STARTED,
                                user_id=st.session_state.get("user_id"),
                                username_snapshot=st.session_state.get("username"),
                                entity_type="backup",
                                entity_id=manifest.get("backup_reference"),
                                outcome="pending",
                            )

                            result = restore_backup(
                                session,
                                engine,
                                db_path,
                                backup_bytes,
                                user_id=st.session_state.get("user_id"),
                            )

                            record_audit_event(
                                session,
                                action=ACTION_RESTORE_COMPLETED,
                                user_id=st.session_state.get("user_id"),
                                username_snapshot=st.session_state.get("username"),
                                entity_type="backup",
                                entity_id=result.get("backup_reference"),
                                outcome="success",
                                metadata_json={
                                    "pre_restore_backup": result.get("pre_restore_reference"),
                                },
                            )

                        st.success(
                            f"✅ Restore completed successfully!\n\n"
                            f"**Backup:** {result.get('backup_reference')}\n"
                            f"**Pre-restore backup:** {result.get('pre_restore_reference')}\n\n"
                            "**⚠️ Please restart the application for changes to take full effect.**"
                        )
                    except (RestoreValidationError, RestoreFailedError) as exc:
                        with session_scope(factory) as session:
                            record_audit_event(
                                session,
                                action=ACTION_RESTORE_FAILED,
                                user_id=st.session_state.get("user_id"),
                                username_snapshot=st.session_state.get("username"),
                                entity_type="backup",
                                outcome="failure",
                                reason_code="RESTORE_FAILED",
                            )
                        render_safe_error(f"Restore failed: {exc}")
                    except Exception as exc:
                        logger.exception("Restore failed unexpectedly")
                        render_safe_error(f"Restore failed: {exc}")
            elif confirmation and confirmation != _RESTORE_PHRASE:
                st.error("Confirmation phrase does not match.")

        except BackupCorruptedError as exc:
            st.error(f"❌ Invalid or corrupted backup: {exc}")
        except BackupHashMismatchError as exc:
            st.error(f"❌ Hash mismatch: {exc}")
        except BackupSchemaMismatchError as exc:
            st.error(f"❌ Schema mismatch: {exc}")
        except Exception as exc:
            render_safe_error(f"Failed to inspect backup: {exc}")


def main() -> None:
    """Backup and restore page — administrator only."""
    configure_page("Backup & Restore")
    require_authentication()
    require_page_access_safe("Backup")
    render_logout_button()
    render_app_header()
    st.subheader("💾 Backup & Restore")
    st.caption("Create database backups and restore from previous backups.")

    # Security notice
    st.info(
        "🔒 **Backup Security** — Backup archives do not include `.env`, "
        "encryption keys, sample files, exported workbooks, or logs. "
        "Store backup files in an encrypted location."
    )

    engine, factory = _get_engine_and_factory()

    _render_database_status()
    st.divider()
    _render_create_backup(engine, factory)
    st.divider()
    _render_backup_history(factory)
    _render_restore(engine, factory)


if __name__ == "__main__":
    main()
