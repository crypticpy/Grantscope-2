"""Notifications admin endpoints -- SMTP config, user preferences, test email, digest history.

Provides admin visibility into email notification configuration, aggregated
user preferences, test email dispatch, and digest batch history.
"""

import asyncio
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.admin_deps import require_admin
from app.deps import get_db, _safe_error
from app.models.db.notification import DigestLog, NotificationPreference
from app.models.db.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _smtp_configured() -> bool:
    """Return True if SMTP environment variables are present."""
    return bool(
        os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")
    )


def _smtp_status() -> Dict[str, Any]:
    """Build a safe representation of SMTP configuration status.

    Never exposes actual credentials -- only whether keys are set.
    """
    return {
        "configured": _smtp_configured(),
        "host_set": bool(os.getenv("SMTP_HOST")),
        "user_set": bool(os.getenv("SMTP_USER")),
        "password_set": bool(os.getenv("SMTP_PASSWORD")),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "from_email": os.getenv("SMTP_FROM_EMAIL", "noreply@grantscope.app"),
    }


# ---------------------------------------------------------------------------
# GET /admin/notifications/config
# ---------------------------------------------------------------------------


@router.get("/admin/notifications/config")
async def get_notification_config(
    _current_user: dict = Depends(require_admin),
):
    """Notification system configuration.

    Returns a flat object matching the frontend NotificationConfig type.
    """
    try:
        smtp_ok = _smtp_configured()
        return {
            "email_enabled": smtp_ok,
            "digest_enabled": True,
            "smtp_configured": smtp_ok,
            "default_frequency": "weekly",
        }
    except Exception as e:
        logger.error("Failed to get notification config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification config", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/notifications/preferences
# ---------------------------------------------------------------------------


@router.get("/admin/notifications/preferences")
async def get_notification_preferences_summary(
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Aggregate user notification preferences.

    Counts how many users have each digest frequency setting
    (daily, weekly, none) and how many users have no preference
    record at all.
    """
    try:
        # Count preferences by digest_frequency
        freq_sql = text(
            """
            SELECT
                coalesce(digest_frequency, 'none') AS frequency,
                count(*) AS user_count
            FROM notification_preferences
            GROUP BY coalesce(digest_frequency, 'none')
            ORDER BY user_count DESC
        """
        )
        freq_rows = (await db.execute(freq_sql)).mappings().all()

        frequency_counts: Dict[str, int] = {}
        total_with_prefs = 0
        for row in freq_rows:
            frequency_counts[row["frequency"]] = row["user_count"]
            total_with_prefs += row["user_count"]

        # Total users in the system
        total_users_result = await db.execute(select(func.count()).select_from(User))
        total_users = total_users_result.scalar() or 0

        # Users without any notification preferences
        users_without_prefs = total_users - total_with_prefs

        return {
            "total_users": total_users,
            "daily_count": frequency_counts.get("daily", 0),
            "weekly_count": frequency_counts.get("weekly", 0),
            "none_count": max(0, users_without_prefs) + frequency_counts.get("none", 0),
        }

    except Exception as e:
        logger.error("Failed to get notification preferences summary: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("notification preferences summary", e),
        ) from e


# ---------------------------------------------------------------------------
# POST /admin/notifications/test-email
# ---------------------------------------------------------------------------


@router.post("/admin/notifications/test-email")
async def send_test_email(
    current_user: dict = Depends(require_admin),
):
    """Send a test email to the admin's email address.

    Uses the configured SMTP settings.  If SMTP is not configured,
    returns a clear error message.
    """
    if not _smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "SMTP is not configured. Set SMTP_HOST, SMTP_USER, and "
                "SMTP_PASSWORD environment variables to enable email sending."
            ),
        )

    admin_email = current_user.get("email")
    if not admin_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email address found for the current admin user.",
        )

    try:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@grantscope.app")

        subject = "GrantScope2 Admin -- Test Email"
        html_content = (
            "<html><body>"
            "<h2>GrantScope2 Test Email</h2>"
            "<p>This is a test email from the GrantScope2 admin panel.</p>"
            f"<p>Sent at: {datetime.now(timezone.utc).isoformat()}</p>"
            f"<p>To: {admin_email}</p>"
            "<p>If you received this email, your SMTP configuration is working correctly.</p>"
            "</body></html>"
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = admin_email
        msg.attach(MIMEText(html_content, "html"))

        def _send_test_email_sync():
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, [admin_email], msg.as_string())

        await asyncio.to_thread(_send_test_email_sync)

        logger.info(
            "Test email sent to %s by admin user %s", admin_email, current_user["id"]
        )

        return {
            "status": "sent",
            "to": admin_email,
            "from": from_email,
            "message": f"Test email sent successfully to {admin_email}.",
        }

    except smtplib.SMTPException as e:
        logger.error("SMTP error sending test email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMTP error: {type(e).__name__} -- check your SMTP configuration.",
        ) from e
    except Exception as e:
        logger.error("Failed to send test email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("test email", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /admin/notifications/digest-history
# ---------------------------------------------------------------------------


@router.get("/admin/notifications/digest-history")
async def get_digest_history(
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    _current_user: dict = Depends(require_admin),
):
    """Recent digest batch results.

    Returns recent digest log entries showing sent digests, errors,
    and aggregate statistics for the last batches.
    """
    try:
        # --- Individual digest log entries (most recent first) ---
        logs_result = await db.execute(
            select(DigestLog)
            .order_by(DigestLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        logs = logs_result.scalars().all()

        # Total count
        total_result = await db.execute(select(func.count()).select_from(DigestLog))
        total = total_result.scalar() or 0

        log_entries = []
        for log in logs:
            log_entries.append(
                {
                    "id": str(log.id),
                    "user_id": str(log.user_id),
                    "digest_type": log.digest_type,
                    "subject": log.subject,
                    "status": log.status,
                    "error_message": log.error_message,
                    "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                    "created_at": (
                        log.created_at.isoformat() if log.created_at else None
                    ),
                }
            )

        # --- Aggregate stats for the last 7 days ---
        stats_sql = text(
            """
            SELECT
                count(*) AS total_digests,
                count(*) FILTER (WHERE status = 'sent') AS sent,
                count(*) FILTER (WHERE status = 'generated') AS generated,
                count(*) FILTER (WHERE status = 'failed') AS failed,
                count(DISTINCT user_id) AS unique_users,
                min(created_at) AS earliest,
                max(created_at) AS latest
            FROM digest_logs
            WHERE created_at >= now() - interval '7 days'
        """
        )
        stats_row = (await db.execute(stats_sql)).one()

        recent_stats = {
            "period": "7_days",
            "total_digests": stats_row.total_digests,
            "sent": stats_row.sent,
            "generated": stats_row.generated,
            "failed": stats_row.failed,
            "unique_users": stats_row.unique_users,
            "earliest": stats_row.earliest.isoformat() if stats_row.earliest else None,
            "latest": stats_row.latest.isoformat() if stats_row.latest else None,
        }

        return {
            "logs": log_entries,
            "total": total,
            "limit": limit,
            "offset": offset,
            "recent_stats": recent_stats,
        }

    except Exception as e:
        logger.error("Failed to get digest history: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("digest history", e),
        ) from e
