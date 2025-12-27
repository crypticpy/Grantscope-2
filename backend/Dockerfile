# =============================================================================
# Foresight API - Production Dockerfile
# =============================================================================
# Hardened container image for Railway deployment
# Security: Non-root user, minimal attack surface, health checks
# =============================================================================

FROM python:3.11-slim

# =============================================================================
# Metadata Labels
# =============================================================================
LABEL maintainer="Foresight Team"
LABEL description="Foresight API - FastAPI backend for Austin Strategic Research System"
LABEL version="1.0.0"

# =============================================================================
# Environment Configuration
# =============================================================================
# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# =============================================================================
# System Dependencies (as root, before switching users)
# =============================================================================
# Install build dependencies and curl for health checks
# Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# =============================================================================
# Security: Create non-root user
# =============================================================================
# Create a dedicated user and group for running the application
# This follows the principle of least privilege
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# =============================================================================
# Python Dependencies (cache layer optimization)
# =============================================================================
# Copy requirements first to leverage Docker layer caching
# Dependencies change less frequently than application code
# Note: Using backend/ prefix because Docker context is repo root
COPY backend/requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size by not caching pip downloads
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Application Code
# =============================================================================
# Copy application code with proper ownership
# Note: Using backend/ prefix because Docker context is repo root
COPY --chown=appuser:appgroup backend/app/ ./app/

# Copy entrypoint (supports web vs worker via FORESIGHT_PROCESS_TYPE)
COPY --chown=appuser:appgroup backend/entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

# =============================================================================
# Switch to Non-Root User
# =============================================================================
# All subsequent commands run as appuser for security
USER appuser

# =============================================================================
# Port Exposure
# =============================================================================
EXPOSE 8000

# =============================================================================
# Health Check
# =============================================================================
# Container health check for orchestration platforms (Railway, Kubernetes, etc.)
# Checks the /api/v1/health endpoint every 30 seconds
# Allows 60 seconds for initial startup (matplotlib font caching takes ~5s)
# NOTE: Uses PORT env var which Railway provides dynamically
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# =============================================================================
# Production Server Command
# =============================================================================
# Use gunicorn with uvicorn workers for production
# - 4 workers: Optimal for most Railway instance sizes (scales with CPU)
# - UvicornWorker: Async ASGI worker for FastAPI
# - Graceful timeout: 30s for clean shutdown on SIGTERM
# - Keep-alive: 5s for connection reuse
# - Access logging: Enabled for observability
#
# IMPORTANT: Railway provides PORT env var dynamically - we MUST use it
# The shell form allows environment variable substitution
CMD ["/app/entrypoint.sh"]
