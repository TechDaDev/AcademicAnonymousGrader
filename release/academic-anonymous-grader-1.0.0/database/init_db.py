# Academic Anonymous Grader — Database Initialization
"""Idempotent database initialization with versioned migrations."""

from __future__ import annotations

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

# Import all models so they register with Base metadata
import models  # noqa: F401 — registers all models
from database.base import Base
from database.migrations import run_migrations


def initialize_database(engine: Engine) -> list[str]:
    """Create all tables if they do not already exist and apply pending migrations.

    This function is idempotent — calling it multiple times will not
    delete or reset existing data.

    It performs two steps:
        1. ``Base.metadata.create_all()`` — creates any missing tables
           from the current model definitions.
        2. ``run_migrations()`` — applies any pending versioned migrations.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine connected to the target database.

    Returns
    -------
    list[str]
        Descriptions of applied migrations.  Empty list if already current.
    """
    Base.metadata.create_all(engine)
    applied = run_migrations(engine)
    return applied


def verify_database_tables(engine: Engine) -> list[str]:
    """Return a list of table names present in the database.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine.

    Returns
    -------
    list[str]
        Sorted list of table names.
    """
    inspector = inspect(engine)
    return sorted(inspector.get_table_names())


def get_table_count(session: Session) -> int:
    """Return the number of tables in the database.

    Parameters
    ----------
    session : Session
        Active database session.

    Returns
    -------
    int
        Number of tables.
    """
    inspector = inspect(session.get_bind())
    return len(inspector.get_table_names())
