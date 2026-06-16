# Academic Anonymous Grader — Bootstrap Administrator Creation
"""CLI script to create the first administrator user.

Usage:
    python -m scripts.create_admin

Prompts for username and password interactively.
Never echoes passwords or prints password hashes.
"""

from __future__ import annotations

import getpass
import sys

# Ensure the project root is on sys.path
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import dotenv  # noqa: E402

dotenv.load_dotenv()

from config import get_settings  # noqa: E402
from database.engine import get_engine  # noqa: E402
from database.init_db import initialize_database  # noqa: E402
from database.session import create_session_factory, session_scope  # noqa: E402
from services.auth_service import create_user  # noqa: E402
from services.exceptions import DuplicateUsernameError, WeakPasswordError  # noqa: E402


def main() -> None:
    """Create the first administrator user interactively."""
    print("=" * 60)
    print("  Academic Anonymous Grader — Bootstrap Admin Creation")
    print("=" * 60)
    print()

    # Load settings and initialize database
    try:
        settings = get_settings()
        engine = get_engine(settings.resolved_database_url(), echo=False)
        initialize_database(engine)
        factory = create_session_factory(engine)
    except Exception as exc:
        print(f"ERROR: Failed to initialize database: {exc}", file=sys.stderr)
        sys.exit(1)

    # Check if an administrator already exists
    from models.user import User  # noqa: E402

    with session_scope(factory) as session:
        existing_admin = session.query(User).filter(User.role == "administrator").first()
        if existing_admin is not None:
            print(f"An administrator already exists (username: '{existing_admin.username}').")
            proceed = input("Create another administrator? (y/N): ").strip().lower()
            if proceed != "y":
                print("Aborted.")
                sys.exit(0)

    # Prompt for credentials
    print("Enter administrator credentials:")
    print()

    username = input("Username: ").strip()
    if not username:
        print("ERROR: Username cannot be empty.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("ERROR: Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("ERROR: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    display_name = input("Display Name (optional): ").strip() or None

    print()
    print("Creating administrator...")

    try:
        with session_scope(factory) as session:
            user = create_user(
                session,
                username=username,
                password=password,
                role="administrator",
                display_name=display_name,
            )
        print()
        print(f"✅ Administrator '{user.username}' created successfully!")
        print(f"   Role: {user.role}")
        if user.display_name:
            print(f"   Display Name: {user.display_name}")
        print()
        print("You can now log in to the application.")
    except WeakPasswordError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except DuplicateUsernameError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Failed to create administrator: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
