# Academic Anonymous Grader — Database Session
"""SQLAlchemy session management with context manager support."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine instance.

    Returns
    -------
    sessionmaker[Session]
        Configured session factory.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on exception.

    Parameters
    ----------
    session_factory : sessionmaker[Session]
        Session factory to use.

    Yields
    ------
    Session
        Active database session.
    """
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
