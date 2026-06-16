"""Idempotent runtime fix: set classification_needs_review for materials.

This script is invoked by docker/entrypoint.sh on every container start.
It corrects the flag for materials that lack any of the four required
classification references (department_id, academic_stage_id,
academic_term_id, academic_year_id).

Safe to run repeatedly — only touches records where the flag is
incorrect (False when it should be True).  Emits counts only, never
material contents, student identities, or reference values.

Usage:
    python -m scripts.fix_classification_review
"""

from __future__ import annotations

import sys

from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.logging_service import get_logger

_logger = get_logger("fix_classification_review")


def fix_classification_review() -> int:
    """Set classification_needs_review for materials missing any ref.

    Returns count of materials corrected.
    """
    settings = get_settings()
    engine = get_engine(settings.resolved_database_url())
    factory = create_session_factory(engine)

    fixed_count = 0
    with session_scope(factory) as session:
        from models.material import Material

        pending = session.query(Material).filter(
            Material.classification_needs_review == False,  # noqa: E712
            (
                (Material.department_id.is_(None))
                | (Material.academic_stage_id.is_(None))
                | (Material.academic_term_id.is_(None))
                | (Material.academic_year_id.is_(None))
            ),
        ).all()

        for m in pending:
            refs = [
                m.department_id,
                m.academic_stage_id,
                m.academic_term_id,
                m.academic_year_id,
            ]
            m.classification_needs_review = not all(r is not None for r in refs)
        fixed_count = len(pending)

    return fixed_count


def main() -> None:
    """Entry point for the script."""
    count = fix_classification_review()
    if count:
        print(f"Fixed classification_needs_review for {count} material(s).")
        _logger.info("Fixed classification_needs_review for %d material(s).", count)
    else:
        print("All materials have correct classification_needs_review.")
    sys.exit(0)


if __name__ == "__main__":
    main()
