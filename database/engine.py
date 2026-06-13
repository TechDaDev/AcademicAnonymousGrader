# Academic Anonymous Grader — Database Engine
"""SQLAlchemy engine creation and configuration."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine, event


def get_engine(database_url: str, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine configured for local SQLite usage.

    Parameters
    ----------
    database_url : str
        Full SQLAlchemy database URL.
    echo : bool
        If True, log all SQL statements (useful for debugging).

    Returns
    -------
    Engine
        Configured SQLAlchemy engine.
    """
    engine = create_engine(
        database_url,
        echo=echo,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection: Any, _connection_record: Any  # noqa: ANN401 — SQLAlchemy event signature
    ) -> None:
        """Enable SQLite foreign key enforcement on every connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    @event.listens_for(engine, "connect")
    def _enable_wal_mode(
        dbapi_connection: Any, _connection_record: Any  # noqa: ANN401 — SQLAlchemy event signature
    ) -> None:
        """Enable WAL mode for better concurrent read performance."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()

    return engine
