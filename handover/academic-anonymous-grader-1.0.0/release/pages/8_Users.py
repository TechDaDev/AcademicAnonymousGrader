# Academic Anonymous Grader — User Management Page
"""Administrator-only user management — create, activate, deactivate, unlock."""

from __future__ import annotations

from typing import Any

import streamlit as st

from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.audit_service import (
    ACTION_USER_CREATED,
    ACTION_USER_DEACTIVATED,
    ACTION_USER_REACTIVATED,
    record_audit_event,
)
from services.auth_service import (
    create_user,
    deactivate_user,
    list_users,
    reactivate_user,
    unlock_user,
)
from services.authorization_service import (
    display_role,
    get_assignable_roles,
    is_legacy_role,
)
from services.exceptions import DuplicateUsernameError, UserNotFoundError, WeakPasswordError
from services.logging_service import get_logger
from ui.layout import configure_page, render_app_header, render_safe_error
from ui.session import render_logout_button, require_authentication, require_page_access_safe

logger = get_logger("users_page")

_VALID_ROLES = ["administrator", "grader", "reviewer", "exporter", "viewer"]


def _get_session_factory() -> Any:  # noqa: ANN401
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url(), echo=settings.app_debug)
    initialize_database(engine)
    return create_session_factory(engine)


def _render_create_user(factory: Any) -> None:  # noqa: ANN401
    """Render the create-user form."""
    with st.expander("➕ Create New User", expanded=False):
        with st.form("create_user_form"):
            username = st.text_input("Username *", placeholder="e.g., jdoe")
            col1, col2 = st.columns(2)
            with col1:
                password = st.text_input("Password *", type="password")
            with col2:
                password_confirm = st.text_input("Confirm Password *", type="password")
            display_name = st.text_input("Display Name", placeholder="Optional display name")
            assignable = get_assignable_roles()  # [(internal, display)]
            role_options = [display_name for _, display_name in assignable]
            role_values = [internal for internal, _ in assignable]
            role = st.selectbox("Role", role_options, index=1)
            submitted = st.form_submit_button("Create User")

        if submitted:
            # Map display name back to internal role
            role_idx = role_options.index(role) if role in role_options else 1
            role_internal = role_values[role_idx]
            if not username or not password:
                st.error("Username and password are required.")
                return
            if password != password_confirm:
                st.error("Passwords do not match.")
                return

            try:
                with session_scope(factory) as session:
                    user = create_user(
                        session,
                        username=username,
                        password=password,
                        role=role_internal,
                        display_name=display_name or None,
                    )
                    record_audit_event(
                        session,
                        action=ACTION_USER_CREATED,
                        user_id=st.session_state.get("user_id"),
                        username_snapshot=st.session_state.get("username"),
                        entity_type="user",
                        entity_id=user.id,
                        outcome="success",
                    )
                st.success(f"User '{username}' created successfully with role '{role}'.")
                st.rerun()
            except WeakPasswordError as exc:
                render_safe_error(str(exc))
            except DuplicateUsernameError as exc:
                render_safe_error(str(exc))
            except Exception:
                logger.exception("Failed to create user")
                render_safe_error("An unexpected error occurred.")


def _render_user_list(factory: Any) -> None:  # noqa: ANN401
    """Render the user list with management actions."""
    st.subheader("👥 User List")

    try:
        with session_scope(factory) as session:
            users = list_users(session)
            current_user_id = st.session_state.get("user_id")

            if not users:
                st.info("No users found.")
                return

            for u in users:
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{u['username']}**")
                        if u["display_name"]:
                            st.caption(u["display_name"])
                    with cols[1]:
                        role_display = display_role(u['role'])
                        legacy_tag = " (legacy)" if is_legacy_role(u['role']) else ""
                        st.caption(f"Role: `{role_display}`{legacy_tag}")

                        # Role conversion for non-self users
                        is_self = u["id"] == current_user_id
                        if not is_self:
                            assignable = get_assignable_roles()
                            current_internal = u['role']
                            # Show conversion options only if role is legacy or different from available
                            assignable_displays = [display_name for internal, display_name in assignable]
                            assignable_internals = [internal for internal, _ in assignable]
                            # Only show if current role is not already in assignable
                            if current_internal not in assignable_internals or True:
                                conv_key = f"role_conv_{u['id']}"
                                current_idx = 0
                                selected = st.selectbox(
                                    "Convert to",
                                    assignable_displays,
                                    index=current_idx,
                                    key=conv_key,
                                    label_visibility="collapsed",
                                )
                                if st.button("Apply Role", key=f"apply_role_{u['id']}", use_container_width=True):
                                    sel_idx = assignable_displays.index(selected)
                                    new_role_internal = assignable_internals[sel_idx]
                                    try:
                                        with session_scope(factory) as s:
                                            from services.auth_service import change_user_role
                                            change_user_role(
                                                s,
                                                str(current_user_id),
                                                u["id"],
                                                new_role_internal,
                                            )
                                            record_audit_event(
                                                s,
                                                action="user_updated",
                                                user_id=current_user_id,
                                                username_snapshot=st.session_state.get("username"),
                                                entity_type="user",
                                                entity_id=u["id"],
                                                outcome="success",
                                                metadata_json={"new_role": new_role_internal},
                                            )
                                        st.rerun()
                                    except (ValueError, UserNotFoundError) as exc:
                                        st.error(str(exc))
                    with cols[2]:
                        status = "✅ Active" if u["is_active"] else "❌ Disabled"
                        st.caption(status)
                    with cols[3]:
                        if u["is_locked"]:
                            st.caption(f"🔒 Locked ({u['failed_login_attempts']} attempts)")
                        else:
                            st.caption(f"Logins: {u['failed_login_attempts']} failed")

                    with cols[4]:
                        if u["last_login_at"]:
                            st.caption(f"Last: {u['last_login_at'].strftime('%Y-%m-%d %H:%M')}")
                        else:
                            st.caption("Never logged in")

                    with cols[5]:
                        is_self = u["id"] == current_user_id
                        if u["is_active"] and not is_self:
                            if st.button("Deactivate", key=f"deact_{u['id']}"):
                                try:
                                    uid_val = str(st.session_state.get("user_id", ""))
                                    with session_scope(factory) as s:
                                        deactivate_user(s, uid_val, u["id"])
                                        record_audit_event(
                                            s,
                                            action=ACTION_USER_DEACTIVATED,
                                            user_id=uid_val,
                                            username_snapshot=st.session_state.get("username"),
                                            entity_type="user",
                                            entity_id=u["id"],
                                            outcome="success",
                                        )
                                    st.rerun()
                                except ValueError as exc:
                                    st.error(str(exc))
                                except UserNotFoundError as exc:
                                    st.error(str(exc))
                        elif not u["is_active"]:
                            if st.button("Reactivate", key=f"react_{u['id']}"):
                                try:
                                    with session_scope(factory) as s:
                                        reactivate_user(s, u["id"])
                                        record_audit_event(
                                            s,
                                            action=ACTION_USER_REACTIVATED,
                                            user_id=current_user_id,
                                            username_snapshot=st.session_state.get("username"),
                                            entity_type="user",
                                            entity_id=u["id"],
                                            outcome="success",
                                        )
                                    st.rerun()
                                except UserNotFoundError as exc:
                                    st.error(str(exc))
                        if u["is_locked"]:
                            if st.button("Unlock", key=f"unlock_{u['id']}"):
                                try:
                                    with session_scope(factory) as s:
                                        unlock_user(s, u["id"])
                                    st.rerun()
                                except UserNotFoundError as exc:
                                    st.error(str(exc))

    except Exception:
        logger.exception("Failed to list users")
        render_safe_error("Could not load user list.")


def main() -> None:
    """User management page — administrator only."""
    configure_page("User Management")
    require_authentication()
    require_page_access_safe("Users")
    render_logout_button()
    render_app_header()
    st.subheader("👤 User Management")
    st.caption("Create, activate, deactivate, and unlock user accounts.")

    factory = _get_session_factory()

    _render_create_user(factory)
    st.divider()
    _render_user_list(factory)
