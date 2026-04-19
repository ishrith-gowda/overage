# Dockerfile — Multi-stage production build for Overage proxy
# Stage 1: Install dependencies in a builder image
# Stage 2: Copy only what's needed into a slim runtime image
# Reference: ARCHITECTURE.md Section 8 (Deployment Architecture)

# ---------------------------------------------------------------------------
# Stage 1: Builder — install Python dependencies
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required for building Python packages
# - gcc/g++: compiling C extensions (e.g., uvloop, numpy)
# - libpq-dev: PostgreSQL client library for asyncpg
# - git: some pip packages install from git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment for clean dependency isolation
RUN python -m venv /opt/venv
# Prefer wheels over sdist compiles on slim images (faster CI/prod builds).
ENV PATH="/opt/venv/bin:$PATH" \
    PIP_PREFER_BINARY=1

# Install Python dependencies
# Copy only dependency files first to maximize Docker layer caching.
# Code changes won't invalidate the dependency layer.
COPY pyproject.toml README.md ./
COPY proxy/__init__.py proxy/__init__.py
# Default: full image with PALACE (torch). CI passes INSTALL_ML=false for fast image checks.
ARG INSTALL_ML=true
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir ".[ml]"; \
    else \
      pip install --no-cache-dir .; \
    fi

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with only what's needed
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="Ishrith Gowda" \
      version="0.1.0" \
      description="Overage — Independent audit layer for LLM reasoning token billing"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default to production settings
    OVERAGE_ENV=production \
    # Bind to all interfaces (required for containerized deployment)
    PROXY_HOST=0.0.0.0 \
    PROXY_PORT=8000

# Install only runtime system dependencies (no build tools)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user for security (never run as root in production)
RUN groupadd --gid 1000 overage && \
    useradd --uid 1000 --gid overage --shell /bin/bash --create-home overage

# Copy application code
WORKDIR /app
COPY proxy/ proxy/
COPY alembic.ini .

# Switch to non-root user
USER overage

# Expose the proxy port
EXPOSE 8000

# Health check — verify the proxy is responsive
# Interval: check every 30s, Timeout: 5s per check, Retries: 3 before unhealthy
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the proxy server via uvicorn
# Workers: 1 for MVP (scale via container replicas, not worker processes)
# Access log disabled: structlog handles all request logging
CMD ["uvicorn", "proxy.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
