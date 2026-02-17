"""Shared dependencies for all GrantScope API routers.

Centralises the Supabase client singleton (for data access during
migration), SQLAlchemy session factory, JWT-based authentication,
HTTPBearer scheme, OpenAI alias, rate-limiter reference, and small
utility helpers so that every router module can
``from app.deps import ...`` without pulling in the heavyweight
``main`` module.
"""

import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from postgrest.exceptions import APIError
from supabase import create_client, Client

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
# Supabase client (singleton) -- kept for data-access queries only;
# authentication is handled by app.auth (JWT).
# ---------------------------------------------------------------------------
_supabase_url = os.getenv("SUPABASE_URL")
_supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
_supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

# Guard missing env vars gracefully for deployments without Supabase
supabase: Optional[Client] = None
if _supabase_url and _supabase_service_key:
    supabase = create_client(_supabase_url, _supabase_service_key)

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


def _is_missing_supabase_table_error(exc: Exception, table_name: str) -> bool:
    """Best-effort detection for missing PostgREST table errors."""
    try:
        if isinstance(exc, APIError):
            message = f"{exc.message or ''} {exc.details or ''}".lower()
        else:
            message = str(exc).lower()
    except Exception:
        return False

    table = table_name.lower()
    if table not in message:
        return False

    return any(
        marker in message
        for marker in (
            "could not find the table",
            "schema cache",
            "does not exist",
            "relation",
            "undefined_table",
        )
    )


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
