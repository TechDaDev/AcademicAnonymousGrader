#!/bin/bash
# Academic Anonymous Grader — Docker Entrypoint
set -eu

# Create required runtime directories
mkdir -p /app/data /app/backups /app/exports /app/logs

# Check file permissions on persistent data directory
if [ ! -w /app/data ]; then
    echo "ERROR: /app/data is not writable." >&2
    exit 1
fi
if [ ! -w /app/backups ]; then
    echo "ERROR: /app/backups is not writable." >&2
    exit 1
fi

# Validate environment (required in production)
if [ "$APP_ENV" = "production" ]; then
    if [ -z "${IDENTITY_ENCRYPTION_KEY:-}" ]; then
        echo "ERROR: IDENTITY_ENCRYPTION_KEY is not set." >&2
        exit 1
    fi
    if [ -z "${IDENTITY_FINGERPRINT_KEY:-}" ]; then
        echo "ERROR: IDENTITY_FINGERPRINT_KEY is not set." >&2
        exit 1
    fi
fi

# Validate configuration
python -c "
from services.config_validation import validate_config_or_exit
validate_config_or_exit()
print('Configuration validation passed.')
"

# Initialize database and apply pending migrations
python -c "
from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
settings = get_settings()
engine = get_engine(settings.resolved_database_url())
applied = initialize_database(engine)
if applied:
    for desc in applied:
        print(f'Migration applied: {desc}')
else:
    print('Database schema is already current.')
"

# Verify schema version
python -c "
from database.engine import get_engine
from database.migrations import verify_schema_version
from config import get_settings
settings = get_settings()
engine = get_engine(settings.resolved_database_url())
healthy, msg = verify_schema_version(engine)
print(f'Schema version check: {msg}')
if not healthy:
    import sys
    print('ERROR: Schema version mismatch.', file=sys.stderr)
    sys.exit(1)
"

# Seed default academic structure (idempotent)
python -c "
from config import get_settings
from database.engine import get_engine
from database.session import create_session_factory, session_scope
from services.academic_structure_service import seed_default_academic_structure
settings = get_settings()
engine = get_engine(settings.resolved_database_url())
factory = create_session_factory(engine)
with session_scope(factory) as session:
    results = seed_default_academic_structure(session)
    for r in results:
        print(f'Seed: {r}')
    if not results:
        print('Academic structure already seeded.')
"

# Fix classification_needs_review flag for materials missing any ref
python -m scripts.fix_classification_review

# Create default Administrator if none exists (first-start bootstrap)
python -c "
from config import get_settings
from database.engine import get_engine
from database.init_db import initialize_database
from database.session import create_session_factory, session_scope
from services.auth_service import create_user
from models.user import User

settings = get_settings()
engine = get_engine(settings.resolved_database_url())
initialize_database(engine)
factory = create_session_factory(engine)

with session_scope(factory) as session:
    admin_count = session.query(User).filter(User.role == 'administrator').count()
    if admin_count == 0:
        # Use environment-provided credentials or safe defaults
        admin_user = create_user(
            session,
            username=__import__('os').environ.get('ADMIN_USERNAME', 'admin'),
            password=__import__('os').environ.get('ADMIN_PASSWORD', 'Admin123!'),
            role='administrator',
            display_name='System Administrator'
        )
        print(f'Default Administrator created: {admin_user.username}')
    else:
        print(f'Administrator already exists ({admin_count}). Skipping bootstrap.')
"

# Execute the supplied command (default: streamlit run app.py ...)
exec "$@"
