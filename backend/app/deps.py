"""Shared dependencies for all Foresight API routers.

Centralises the Supabase client singleton, authentication dependency,
HTTPBearer scheme, OpenAI alias, rate-limiter reference, and small
utility helpers so that every router module can ``from app.deps import …``
without pulling in the heavyweight ``main`` module.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
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
# Supabase client (singleton)
# ---------------------------------------------------------------------------
_supabase_url = os.getenv("SUPABASE_URL")
_supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
_supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

# Guard missing env vars gracefully for Vercel preview deployments
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
    """Log the full exception but return a safe message without internal details.

    This prevents leaking stack traces, file paths, or database internals
    to API consumers while preserving full diagnostics in server logs.
    """
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
# Authentication dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current authenticated user with security logging.

    Validates JWT token via Supabase Auth, which handles:
    - Token signature verification
    - Token expiration checking
    - Token revocation status

    Security features:
    - Logs authentication failures with client IP for audit
    - Returns generic error messages to prevent user enumeration
    - Rate limited at the endpoint level
    """
    try:
        token = credentials.credentials

        # Validate token is not empty and has reasonable length
        if not token or len(token) < 20:
            log_security_event("auth_invalid_token_format", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        # Validate token with Supabase Auth (handles signature, expiration, revocation)
        response = supabase.auth.get_user(token)

        if response.user:
            # Get user profile
            profile_response = (
                supabase.table("users").select("*").eq("id", response.user.id).execute()
            )
            if profile_response.data:
                # Log successful auth for audit trail (info level, not warning)
                logger.debug(f"Authenticated user: {response.user.id}")
                return profile_response.data[0]
            else:
                # User exists in auth but not in users table - potential issue
                logger.warning(
                    f"User profile not found for authenticated user_id: {response.user.id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found",
                )
        else:
            # Token was valid format but not a valid session
            log_security_event("auth_invalid_session", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

    except HTTPException:
        raise
    except Exception as e:
        # Log the actual error for debugging but return generic message
        log_security_event(
            "auth_error",
            request,
            {"error_type": type(e).__name__, "error_msg": str(e)[:100]},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e
