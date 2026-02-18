"""Shared dependencies for all GrantScope API routers.

Centralises the SQLAlchemy session factory, JWT-based authentication,
HTTPBearer scheme, OpenAI alias, rate-limiter reference, and small
utility helpers so that every router module can
``from app.deps import ...`` without pulling in the heavyweight
``main`` module.
"""

import logging

from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.openai_provider import (
    azure_openai_client,
    azure_openai_embedding_client,
    get_chat_deployment,
    get_chat_mini_deployment,
    get_embedding_deployment,
)
from app.security import (
    get_rate_limiter,
    rate_limit_sensitive,
    rate_limit_auth,
    rate_limit_discovery,
    log_security_event,
    get_client_ip,
)

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI alias
# ---------------------------------------------------------------------------
openai_client = azure_openai_client

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = get_rate_limiter()

# ---------------------------------------------------------------------------
# HTTPBearer security scheme
# ---------------------------------------------------------------------------
security = HTTPBearer()

# ---------------------------------------------------------------------------
# Small utility helpers
# ---------------------------------------------------------------------------


def _safe_error(operation: str, e: Exception) -> str:
    """Log the full exception but return a safe message without internal details."""
    logger.exception("Error during %s", operation)
    return f"{operation} failed. Please try again or contact support."


# ---------------------------------------------------------------------------
# Authentication dependency -- JWT-based (no Supabase auth)
# ---------------------------------------------------------------------------
# Import the JWT-based ``get_current_user`` from app.auth so that all
# routers that do ``from app.deps import get_current_user`` automatically
# get the new implementation without any per-router changes.

from app.auth import get_current_user  # noqa: E402
from app.auth import get_current_user_hardcoded  # noqa: E402

# ---------------------------------------------------------------------------
# SQLAlchemy async session dependency (Azure PostgreSQL)
# ---------------------------------------------------------------------------
from app.database import get_db  # noqa: E402
