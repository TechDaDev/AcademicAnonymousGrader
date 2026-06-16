# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ARG UID=1000
ARG GID=1000

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency metadata first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

# Install only runtime system packages (no curl — health check uses python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with configurable UID/GID
RUN groupadd -g "$GID" grader && \
    useradd -l -u "$UID" -g "$GID" -d /app -s /bin/bash grader && \
    mkdir -p /app/data /app/backups /app/exports /app/logs && \
    chown -R grader:grader /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source (dockerignore excludes secrets, data, samples)
COPY --chown=grader:grader . .

# Ensure directories exist with correct permissions
RUN mkdir -p /app/data /app/backups /app/exports /app/logs && \
    chown -R grader:grader /app && \
    chmod +x /app/docker/entrypoint.sh

USER grader

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -m scripts.health_check || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
