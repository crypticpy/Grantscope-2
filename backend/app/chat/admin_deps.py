"""Admin authentication dependencies for FastAPI endpoints.

Provides reusable Depends() callables for admin-only endpoints so that
individual routers do not need to repeat the role-checking boilerplate.
"""

from fastapi import Depends, HTTPException, status

from app.auth import get_current_user_hardcoded


async def require_admin(
    current_user: dict = Depends(get_current_user_hardcoded),
) -> dict:
    """FastAPI dependency that enforces admin-level access.

    Raises :class:`~fastapi.HTTPException` with status 403 if the
    authenticated user does not have the ``admin`` or ``service_role`` role.

    Usage::

        @router.get("/admin/something")
        async def admin_endpoint(
            user: dict = Depends(require_admin),
        ):
            ...
    """
    user_role = current_user.get("role", "")
    if user_role not in ("admin", "service_role"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
