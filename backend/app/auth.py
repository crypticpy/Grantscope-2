"""Hardcoded authentication system for GrantScope2.

Provides JWT-based authentication with a small set of hardcoded users.
Passwords are verified with bcrypt. Tokens are signed with HS256 via
python-jose.

When Entra ID / Azure AD is enabled, replace ``authenticate_user`` and
``get_current_user`` with real identity-provider integration.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "gs2-dev-secret-change-in-production-2026",
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


# ---------------------------------------------------------------------------
# Password hashing (direct bcrypt, avoids passlib compatibility issues)
# ---------------------------------------------------------------------------
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Hardcoded users
# ---------------------------------------------------------------------------
# Passwords are bcrypt-hashed at module load time so the plain-text values
# never appear in memory after startup.

HARDCODED_USERS: dict[str, dict[str, Any]] = {
    "admin@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "admin@grantscope.gov",
        "display_name": "Admin User",
        "department": "APH",
        "role": "admin",
        "hashed_password": _hash_password("GS2Admin2026!"),
        "created_at": "2026-01-01T00:00:00+00:00",
    },
    "chris@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000002",
        "email": "chris@grantscope.gov",
        "display_name": "Chris Martinez",
        "department": "APH",
        "role": "admin",
        "hashed_password": _hash_password("GS2Chris2026!"),
        "created_at": "2026-01-01T00:00:00+00:00",
    },
    "test@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000003",
        "email": "test@grantscope.gov",
        "display_name": "Test User",
        "department": "APH",
        "role": "user",
        "hashed_password": _hash_password("GS2Test2026!"),
        "created_at": "2026-01-01T00:00:00+00:00",
    },
    "phillip@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000004",
        "email": "phillip@grantscope.gov",
        "display_name": "Phillip",
        "department": "APH",
        "role": "user",
        "hashed_password": _hash_password("Granite$cope4P!"),
        "created_at": "2026-02-18T00:00:00+00:00",
    },
    "brian@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000005",
        "email": "brian@grantscope.gov",
        "display_name": "Brian",
        "department": "APH",
        "role": "user",
        "hashed_password": _hash_password("Granite$cope5B!"),
        "created_at": "2026-02-18T00:00:00+00:00",
    },
    "tracy@grantscope.gov": {
        "id": "00000000-0000-0000-0000-000000000006",
        "email": "tracy@grantscope.gov",
        "display_name": "Tracy",
        "department": "APH",
        "role": "user",
        "hashed_password": _hash_password("Granite$cope6T!"),
        "created_at": "2026-02-18T00:00:00+00:00",
    },
}

# ---------------------------------------------------------------------------
# HTTPBearer scheme (shared with deps.py)
# ---------------------------------------------------------------------------
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _user_profile(user_record: dict[str, Any]) -> dict[str, Any]:
    """Return a user dict without the hashed password."""
    return {k: v for k, v in user_record.items() if k != "hashed_password"}


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    """Verify *email* and *password* against the hardcoded user list.

    Returns the user profile dict (without password) on success, or
    ``None`` if authentication fails.
    """
    user = HARDCODED_USERS.get(email.lower().strip())
    if user is None:
        return None
    if not _verify_password(password, user["hashed_password"]):
        return None
    return _user_profile(user)


def create_access_token(user_data: dict[str, Any]) -> str:
    """Create a signed JWT containing the user's id and email."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = None,
) -> dict[str, Any]:
    """FastAPI dependency -- extract and validate the Bearer JWT.

    Can be used as ``Depends(get_current_user)`` in route signatures.
    If *credentials* is not supplied (e.g. when called manually), we
    fall back to reading the ``Authorization`` header directly.
    """
    token: str | None = None

    # Prefer credentials injected by HTTPBearer
    if credentials is not None:
        token = credentials.credentials
    else:
        # Manual fallback
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub", "")
        email: str = payload.get("email", "")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except JWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Look up the full profile from the hardcoded list
    user = HARDCODED_USERS.get(email)
    if user is not None:
        return _user_profile(user)

    # If the token is valid but the email is not in the hardcoded list,
    # return a minimal profile built from the JWT claims so routers
    # that only need ``user["id"]`` still work.
    return {
        "id": user_id,
        "email": email,
        "display_name": email.split("@")[0],
        "department": "Unknown",
        "role": "user",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Backward-compatible alias used by SQLAlchemy-based routers
# ---------------------------------------------------------------------------
async def get_current_user_hardcoded(request: Request) -> dict[str, Any]:
    """Alias for ``get_current_user`` that works without the HTTPBearer
    ``Depends`` -- reads the Authorization header directly from the request.

    Used by newer SQLAlchemy-based routers (checklist, budget, attachments,
    exports, collaboration, applications) that were previously wired to the
    old ``get_current_user_hardcoded`` which returned a fixed user.
    """
    return await get_current_user(request)
