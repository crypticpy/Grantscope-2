"""
Digest Service for GrantScope2 Application.

Generates periodic email digests summarizing new signals, velocity changes,
pattern insights, and workstream updates for each user.

Key Features:
- User-configurable notification email (separate from auth email)
- Configurable frequency (daily, weekly, or disabled)
- LLM-generated digest HTML via Azure OpenAI
- Batch processing for all users due for a digest
- SMTP sending stub (logs output; configure SMTP later)

Usage:
    from app.digest_service import DigestService

    service = DigestService(db, openai_client)
    digest = await service.generate_user_digest(user_id)
    await service.send_digest_email(to_email, digest["subject"], digest["html"])
"""

import json
import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.analytics import CachedInsight, PatternInsight
from app.models.db.card import Card
from app.models.db.card_extras import CardFollow, CardScoreHistory
from app.models.db.notification import DigestLog, NotificationPreference
from app.models.db.user import User
from app.models.db.workstream import Workstream, WorkstreamCard, WorkstreamScan

from app.openai_provider import get_chat_mini_deployment

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Day-of-week mapping for weekly digest scheduling
DAY_OF_WEEK_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
}

# How far back to look for "new" items when no last_digest_sent_at exists
DEFAULT_LOOKBACK_DAYS = 7

# Maximum signals to include in a single digest
MAX_NEW_SIGNALS = 20
MAX_VELOCITY_CHANGES = 10
MAX_PATTERN_INSIGHTS = 5
MAX_WORKSTREAM_UPDATES = 10


# ============================================================================
# Digest Email Prompt
# ============================================================================

DIGEST_EMAIL_PROMPT = """You are an AI assistant for GrantScope2, the City of Austin's
strategic horizon scanning system. Generate a clean, professional HTML email digest
from the structured data below.

The email should be scannable, mobile-friendly, and use a clean design with:
- A clear header with the GrantScope2 brand
- Sections only for data that exists (skip empty sections)
- Signal names as bold links where possible
- Velocity arrows (up/down indicators) for score changes
- A brief AI-generated insight paragraph at the top summarizing the key takeaways
- A footer with unsubscribe/preference link placeholder

Use inline CSS only (no external stylesheets). Keep the color palette professional:
primary blue (#2563EB), dark text (#1F2937), light backgrounds (#F9FAFB),
accent green (#059669) for positive changes, accent red (#DC2626) for declines.

DIGEST DATA:
{digest_json}

PERIOD: {period_label}

Generate ONLY the HTML email body (starting with <html>). Do not include explanation."""


# ============================================================================
# DigestService Class
# ============================================================================


class DigestService:
    """
    Service for generating and sending periodic email digests.

    Handles:
    - Querying user workstreams and signals for digest content
    - Detecting new signals since last digest
    - Detecting velocity/score changes
    - Including pattern insights
    - Generating HTML email via LLM
    - Sending via SMTP (stub for now)
    """

    def __init__(self, db: AsyncSession, openai_client):
        """
        Initialize the DigestService.

        Args:
            db: SQLAlchemy async session for database operations
            openai_client: OpenAI client for LLM-powered email generation
        """
        self.db = db
        self.openai_client = openai_client

    # ========================================================================
    # Core Digest Generation
    # ========================================================================

    async def generate_user_digest(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate a digest for a single user.

        Queries the user's workstreams, signals, score history, and pattern
        insights to produce structured digest data, then uses the LLM to
        render it as a clean HTML email.

        Args:
            user_id: The user's UUID

        Returns:
            Dict with keys: subject, html_content, summary_json, sections_included
            Returns None if there is nothing to report.
        """
        logger.info(f"Generating digest for user {user_id}")

        # 1. Get user preferences
        prefs = await self._get_user_preferences(user_id)
        if not prefs or prefs.get("digest_frequency") == "none":
            logger.info(f"User {user_id} has digests disabled, skipping")
            return None

        # 2. Determine lookback window
        since = self._get_lookback_since(prefs)

        # 3. Gather digest sections based on user preferences
        sections = {}

        if prefs.get("include_new_signals", True):
            new_signals = await self._get_new_signals(user_id, since)
            if new_signals:
                sections["new_signals"] = new_signals

        if prefs.get("include_velocity_changes", True):
            velocity_changes = await self._get_velocity_changes(user_id, since)
            if velocity_changes:
                sections["velocity_changes"] = velocity_changes

        if prefs.get("include_pattern_insights", True):
            pattern_insights = await self._get_pattern_insights(since)
            if pattern_insights:
                sections["pattern_insights"] = pattern_insights

        if prefs.get("include_workstream_updates", True):
            workstream_updates = await self._get_workstream_updates(user_id, since)
            if workstream_updates:
                sections["workstream_updates"] = workstream_updates

        # 4. If nothing to report, skip
        if not sections:
            logger.info(f"No digest content for user {user_id}, skipping")
            return None

        # 5. Build period label
        period_label = self._build_period_label(since)

        # 6. Generate HTML via LLM
        summary_json = {
            "user_id": user_id,
            "period_start": since.isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "sections": sections,
        }

        subject = f"Your GrantScope2 Intelligence Digest — {period_label}"
        html_content = await self._generate_html_email(summary_json, period_label)

        # 7. Store digest log
        await self._store_digest_log(user_id, subject, html_content, summary_json)

        # 8. Update last_digest_sent_at
        await self._update_last_digest_sent(user_id)

        return {
            "subject": subject,
            "html_content": html_content,
            "summary_json": summary_json,
            "sections_included": list(sections.keys()),
        }

    # ========================================================================
    # Data Gathering Methods
    # ========================================================================

    async def _get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get notification preferences for a user, or None if not configured."""
        try:
            result = await self.db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id
                )
            )
            pref = result.scalar_one_or_none()
            if pref is None:
                return None
            return {
                "digest_frequency": pref.digest_frequency,
                "digest_day": pref.digest_day,
                "include_new_signals": pref.include_new_signals,
                "include_velocity_changes": pref.include_velocity_changes,
                "include_pattern_insights": pref.include_pattern_insights,
                "include_workstream_updates": pref.include_workstream_updates,
                "last_digest_sent_at": (
                    pref.last_digest_sent_at.isoformat()
                    if pref.last_digest_sent_at
                    else None
                ),
                "notification_email": pref.notification_email,
                "user_id": str(pref.user_id),
            }
        except Exception as e:
            logger.error(f"Failed to get notification preferences for {user_id}: {e}")
            return None

    async def _get_new_signals(
        self, user_id: str, since: datetime
    ) -> List[Dict[str, Any]]:
        """
        Find new signals (cards) added to the user's workstreams since the
        last digest, plus newly followed cards.
        """
        results = []

        try:
            # Get user's workstream IDs
            ws_result = await self.db.execute(
                select(Workstream.id, Workstream.name).where(
                    Workstream.user_id == user_id
                )
            )
            workstreams = ws_result.all()
            if ws_map := {str(ws.id): ws.name for ws in workstreams}:
                # Get cards added to workstreams since last digest
                ws_ids = [ws.id for ws in workstreams]
                wc_result = await self.db.execute(
                    select(
                        WorkstreamCard.card_id,
                        WorkstreamCard.workstream_id,
                        WorkstreamCard.added_at,
                        Card.name,
                        Card.summary,
                        Card.pillar_id,
                        Card.horizon,
                        Card.stage_id,
                    )
                    .join(Card, Card.id == WorkstreamCard.card_id)
                    .where(WorkstreamCard.workstream_id.in_(ws_ids))
                    .where(WorkstreamCard.added_at >= since)
                    .order_by(WorkstreamCard.added_at.desc())
                    .limit(MAX_NEW_SIGNALS)
                )

                for wc in wc_result.all():
                    results.append(
                        {
                            "name": wc.name or "Unknown Signal",
                            "summary": wc.summary or "",
                            "pillar": wc.pillar_id or "",
                            "horizon": wc.horizon or "",
                            "stage": wc.stage_id or "",
                            "workstream": ws_map.get(str(wc.workstream_id), ""),
                            "added_at": wc.added_at.isoformat() if wc.added_at else "",
                        }
                    )

            # Also get newly followed cards
            follows_result = await self.db.execute(
                select(
                    CardFollow.card_id,
                    CardFollow.created_at,
                    Card.name,
                    Card.summary,
                    Card.pillar_id,
                )
                .join(Card, Card.id == CardFollow.card_id)
                .where(CardFollow.user_id == user_id)
                .where(CardFollow.created_at >= since)
                .order_by(CardFollow.created_at.desc())
                .limit(MAX_NEW_SIGNALS)
            )

            for follow in follows_result.all():
                card_name = follow.name or "Unknown Signal"
                # Avoid duplicates with workstream cards
                if all(r["name"] != card_name for r in results):
                    results.append(
                        {
                            "name": card_name,
                            "summary": follow.summary or "",
                            "pillar": follow.pillar_id or "",
                            "source": "followed",
                            "added_at": (
                                follow.created_at.isoformat()
                                if follow.created_at
                                else ""
                            ),
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to get new signals for {user_id}: {e}")

        return results[:MAX_NEW_SIGNALS]

    async def _get_velocity_changes(
        self, user_id: str, since: datetime
    ) -> List[Dict[str, Any]]:
        """
        Detect velocity changes for cards the user follows or has in workstreams.
        Compares latest scores to scores at the start of the period.
        """
        results = []

        try:
            # Get card IDs the user cares about (followed + workstream)
            card_ids = await self._get_user_card_ids(user_id)
            if not card_ids:
                return results

            # Batch card_ids to avoid overly large IN queries
            batch_size = 50
            for i in range(0, len(card_ids), batch_size):
                batch = card_ids[i : i + batch_size]

                # Get score history entries for this period
                history_result = await self.db.execute(
                    select(
                        CardScoreHistory.card_id,
                        CardScoreHistory.velocity_score,
                        CardScoreHistory.impact_score,
                        CardScoreHistory.relevance_score,
                        CardScoreHistory.recorded_at,
                    )
                    .where(CardScoreHistory.card_id.in_(batch))
                    .where(CardScoreHistory.recorded_at >= since)
                    .order_by(CardScoreHistory.recorded_at.asc())
                )

                # Group by card_id
                history_by_card: Dict[str, list] = {}
                for entry in history_result.all():
                    cid = str(entry.card_id)
                    if cid not in history_by_card:
                        history_by_card[cid] = []
                    history_by_card[cid].append(entry)

                # Get current card details
                if history_by_card:
                    cards_result = await self.db.execute(
                        select(
                            Card.id,
                            Card.name,
                            Card.velocity_score,
                            Card.impact_score,
                            Card.relevance_score,
                            Card.pillar_id,
                        ).where(Card.id.in_(list(history_by_card.keys())))
                    )
                    card_details = {str(c.id): c for c in cards_result.all()}

                    for cid, entries in history_by_card.items():
                        if len(entries) < 2:
                            continue

                        card = card_details.get(cid)
                        first = entries[0]
                        last = entries[-1]

                        # Calculate velocity change
                        v_old = first.velocity_score or 0
                        v_new = last.velocity_score or 0
                        v_delta = float(v_new) - float(v_old)

                        if abs(v_delta) >= 5:  # Significant change threshold
                            direction = "accelerating" if v_delta > 0 else "declining"
                            results.append(
                                {
                                    "name": card.name if card else "Unknown",
                                    "pillar": card.pillar_id if card else "",
                                    "direction": direction,
                                    "velocity_change": v_delta,
                                    "velocity_current": float(v_new),
                                    "velocity_previous": float(v_old),
                                }
                            )

            # Sort by absolute change magnitude
            results.sort(key=lambda x: abs(x.get("velocity_change", 0)), reverse=True)

        except Exception as e:
            logger.error(f"Failed to get velocity changes for {user_id}: {e}")

        return results[:MAX_VELOCITY_CHANGES]

    async def _get_pattern_insights(self, since: datetime) -> List[Dict[str, Any]]:
        """
        Get recent pattern insights (from cached_insights or pattern_insights
        tables if available).
        """
        results = []

        try:
            # Try pattern_insights table first
            try:
                pi_result = await self.db.execute(
                    select(PatternInsight)
                    .where(PatternInsight.created_at >= since)
                    .order_by(PatternInsight.confidence_score.desc())
                    .limit(MAX_PATTERN_INSIGHTS)
                )
                for pi in pi_result.scalars().all():
                    results.append(
                        {
                            "title": pi.title or "",
                            "summary": pi.description
                            or (pi.summary if hasattr(pi, "summary") else "")
                            or "",
                            "pattern_type": pi.pattern_type or "",
                            "affected_pillars": pi.affected_pillars or [],
                            "confidence": pi.confidence_score or 0,
                        }
                    )
            except Exception:
                # pattern_insights table may not exist yet
                pass

            # Fall back to cached_insights if no pattern insights found
            if not results:
                try:
                    ci_result = await self.db.execute(
                        select(CachedInsight.insights_json, CachedInsight.generated_at)
                        .where(CachedInsight.generated_at >= since)
                        .order_by(CachedInsight.generated_at.desc())
                        .limit(1)
                    )
                    row = ci_result.first()
                    if row:
                        insights_json = row.insights_json or {}
                        insights_list = (
                            insights_json
                            if isinstance(insights_json, list)
                            else insights_json.get("insights", [])
                        )
                        results.extend(
                            {
                                "title": insight.get("title", ""),
                                "summary": insight.get(
                                    "summary", insight.get("description", "")
                                ),
                                "pattern_type": "ai_insight",
                                "affected_pillars": insight.get(
                                    "affected_pillars",
                                    insight.get("pillars", []),
                                ),
                            }
                            for insight in insights_list[:MAX_PATTERN_INSIGHTS]
                        )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Failed to get pattern insights: {e}")

        return results

    async def _get_workstream_updates(
        self, user_id: str, since: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get updates for the user's workstreams: new cards added, scans completed.
        """
        results = []

        try:
            # Get user workstreams
            ws_result = await self.db.execute(
                select(Workstream.id, Workstream.name, Workstream.updated_at).where(
                    Workstream.user_id == user_id
                )
            )
            workstreams = ws_result.all()

            for ws in workstreams:
                ws_update: Dict[str, Any] = {
                    "name": ws.name,
                    "workstream_id": str(ws.id),
                }

                # Count new cards added since last digest
                try:
                    cards_count_result = await self.db.execute(
                        select(func.count(WorkstreamCard.id))
                        .where(WorkstreamCard.workstream_id == ws.id)
                        .where(WorkstreamCard.added_at >= since)
                    )
                    ws_update["new_cards_count"] = cards_count_result.scalar() or 0
                except Exception:
                    ws_update["new_cards_count"] = 0

                # Check for completed scans
                try:
                    scans_result = await self.db.execute(
                        select(func.count(WorkstreamScan.id))
                        .where(WorkstreamScan.workstream_id == ws.id)
                        .where(WorkstreamScan.status == "completed")
                        .where(WorkstreamScan.completed_at >= since)
                    )
                    ws_update["scans_completed"] = scans_result.scalar() or 0
                except Exception:
                    ws_update["scans_completed"] = 0

                # Only include if there's something to report
                if ws_update["new_cards_count"] > 0 or ws_update["scans_completed"] > 0:
                    results.append(ws_update)

        except Exception as e:
            logger.error(f"Failed to get workstream updates for {user_id}: {e}")

        return results[:MAX_WORKSTREAM_UPDATES]

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _get_user_card_ids(self, user_id: str) -> List[str]:
        """Get all card IDs the user is tracking (follows + workstreams)."""
        card_ids = set()

        try:
            # Followed cards
            follows_result = await self.db.execute(
                select(CardFollow.card_id).where(CardFollow.user_id == user_id)
            )
            for f in follows_result.scalars().all():
                card_ids.add(str(f))

            # Workstream cards
            ws_result = await self.db.execute(
                select(Workstream.id).where(Workstream.user_id == user_id)
            )
            ws_ids = [ws_id for ws_id in ws_result.scalars().all()]
            if ws_ids:
                wc_result = await self.db.execute(
                    select(WorkstreamCard.card_id).where(
                        WorkstreamCard.workstream_id.in_(ws_ids)
                    )
                )
                for wc in wc_result.scalars().all():
                    card_ids.add(str(wc))

        except Exception as e:
            logger.error(f"Failed to get user card IDs for {user_id}: {e}")

        return list(card_ids)

    def _get_lookback_since(self, prefs: Dict[str, Any]) -> datetime:
        """Determine the start of the digest period based on preferences."""
        if last_sent := prefs.get("last_digest_sent_at"):
            if isinstance(last_sent, str):
                try:
                    return datetime.fromisoformat(last_sent.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Default lookback based on frequency
        freq = prefs.get("digest_frequency", "weekly")
        days = 1 if freq == "daily" else DEFAULT_LOOKBACK_DAYS
        return datetime.now(timezone.utc) - timedelta(days=days)

    def _build_period_label(self, since: datetime) -> str:
        """Build a human-readable period label for the digest subject line."""
        now = datetime.now(timezone.utc)
        delta = now - since

        if delta.days <= 1:
            return f"Daily Update — {now.strftime('%b %d, %Y')}"
        elif delta.days <= 7:
            return f"Week of {since.strftime('%b %d, %Y')}"
        else:
            return f"{since.strftime('%b %d')} — {now.strftime('%b %d, %Y')}"

    # ========================================================================
    # LLM Email Generation
    # ========================================================================

    async def _generate_html_email(
        self, summary_json: Dict[str, Any], period_label: str
    ) -> str:
        """
        Generate a clean HTML email using the LLM.

        Falls back to a simple template if LLM fails.
        """
        try:
            prompt = DIGEST_EMAIL_PROMPT.format(
                digest_json=json.dumps(summary_json, indent=2, default=str),
                period_label=period_label,
            )

            response = self.openai_client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an HTML email designer. Generate clean, "
                            "professional HTML emails with inline CSS."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            html = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if html.startswith("```html"):
                html = html[7:]
            if html.startswith("```"):
                html = html[3:]
            if html.endswith("```"):
                html = html[:-3]

            return html.strip()

        except Exception as e:
            logger.error(f"LLM email generation failed, using fallback: {e}")
            return self._generate_fallback_html(summary_json, period_label)

    def _generate_fallback_html(
        self, summary_json: Dict[str, Any], period_label: str
    ) -> str:
        """Generate a simple fallback HTML email without the LLM."""
        sections = summary_json.get("sections", {})
        parts = [
            f"""<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  max-width: 600px; margin: 0 auto; padding: 20px; color: #1F2937;">
<div style="background: #2563EB; color: white; padding: 24px; border-radius: 8px 8px 0 0;">
  <h1 style="margin: 0; font-size: 22px;">GrantScope2 Intelligence Digest</h1>
  <p style="margin: 8px 0 0; opacity: 0.9;">{period_label}</p>
</div>
<div style="border: 1px solid #E5E7EB; border-top: none; padding: 24px;
  border-radius: 0 0 8px 8px;">"""
        ]

        if new_signals := sections.get("new_signals", []):
            parts.append(
                '<h2 style="color: #2563EB; border-bottom: 2px solid #E5E7EB; '
                f'padding-bottom: 8px;">New Signals ({len(new_signals)})</h2><ul>'
            )
            for sig in new_signals:
                pillar = sig.get("pillar", "")
                pillar_badge = (
                    f' <span style="background: #EFF6FF; color: #2563EB; '
                    f'padding: 2px 8px; border-radius: 12px; font-size: 12px;">'
                    f"{pillar}</span>"
                    if pillar
                    else ""
                )
                parts.append(
                    f'<li style="margin-bottom: 12px;">'
                    f'<strong>{sig.get("name", "")}</strong>{pillar_badge}'
                    f'<br><span style="color: #6B7280; font-size: 14px;">'
                    f'{sig.get("summary", "")[:200]}</span></li>'
                )
            parts.append("</ul>")

        if velocity := sections.get("velocity_changes", []):
            parts.append(
                '<h2 style="color: #2563EB; border-bottom: 2px solid #E5E7EB; '
                f'padding-bottom: 8px;">Velocity Changes ({len(velocity)})</h2><ul>'
            )
            for vc in velocity:
                direction = vc.get("direction", "")
                arrow = "&#8593;" if direction == "accelerating" else "&#8595;"
                color = "#059669" if direction == "accelerating" else "#DC2626"
                change = vc.get("velocity_change", 0)
                sign = "+" if change > 0 else ""
                parts.append(
                    f'<li style="margin-bottom: 8px;">'
                    f'<strong>{vc.get("name", "")}</strong> '
                    f'<span style="color: {color};">{arrow} {direction.title()}'
                    f" ({sign}{change} pts)</span></li>"
                )
            parts.append("</ul>")

        if patterns := sections.get("pattern_insights", []):
            parts.append(
                '<h2 style="color: #2563EB; border-bottom: 2px solid #E5E7EB; '
                f'padding-bottom: 8px;">AI Insights ({len(patterns)})</h2><ul>'
            )
            for p in patterns:
                pillars_str = ", ".join(p.get("affected_pillars", []))
                affects = (
                    f' — <span style="color: #6B7280;">Affects: {pillars_str}</span>'
                    if pillars_str
                    else ""
                )
                parts.append(
                    f'<li style="margin-bottom: 12px;">'
                    f'<strong>{p.get("title", "")}</strong>{affects}'
                    f'<br><span style="color: #6B7280; font-size: 14px;">'
                    f'{p.get("summary", "")[:200]}</span></li>'
                )
            parts.append("</ul>")

        if ws_updates := sections.get("workstream_updates", []):
            parts.append(
                '<h2 style="color: #2563EB; border-bottom: 2px solid #E5E7EB; '
                'padding-bottom: 8px;">Your Workstreams</h2><ul>'
            )
            for ws in ws_updates:
                details = []
                nc = ws.get("new_cards_count", 0)
                sc = ws.get("scans_completed", 0)
                if nc:
                    details.append(f"{nc} new signal{'s' if nc != 1 else ''} added")
                if sc:
                    details.append(f"{sc} scan{'s' if sc != 1 else ''} completed")
                parts.append(
                    f'<li style="margin-bottom: 8px;">'
                    f'<strong>{ws.get("name", "")}</strong>: '
                    f'{", ".join(details)}</li>'
                )
            parts.append("</ul>")

        parts.append(
            """<hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;">
<p style="color: #9CA3AF; font-size: 12px; text-align: center;">
  This digest was generated by GrantScope2, the City of Austin's strategic
  horizon scanning system.<br>
  <a href="#" style="color: #6B7280;">Manage notification preferences</a>
</p>
</div></body></html>"""
        )

        return "\n".join(parts)

    # ========================================================================
    # Email Sending (Stub)
    # ========================================================================

    async def send_digest_email(
        self, to_email: str, subject: str, html_content: str
    ) -> bool:
        """
        Send a digest email.

        Currently a stub that logs the email. Configure SMTP settings via
        environment variables when ready:
        - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email body

        Returns:
            True if sent (or logged) successfully, False otherwise
        """
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("SMTP_FROM_EMAIL", "noreply@grantscope.app")

        if smtp_host and smtp_user and smtp_password:
            # Real SMTP sending
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = from_email
                msg["To"] = to_email
                msg.attach(MIMEText(html_content, "html"))

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(from_email, [to_email], msg.as_string())

                logger.info(f"Digest email sent to {to_email}: {subject}")
                return True
            except Exception as e:
                logger.error(f"Failed to send digest email to {to_email}: {e}")
                return False
        else:
            # Stub: log the email instead of sending
            logger.info(
                f"[DIGEST STUB] Would send email to {to_email}\n"
                f"  Subject: {subject}\n"
                f"  HTML length: {len(html_content)} chars\n"
                f"  (Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD to enable sending)"
            )
            return True

    # ========================================================================
    # Digest Storage
    # ========================================================================

    async def _store_digest_log(
        self,
        user_id: str,
        subject: str,
        html_content: str,
        summary_json: Dict[str, Any],
    ) -> None:
        """Store a record of the generated digest for audit and retry."""
        try:
            log = DigestLog(
                user_id=user_id,
                digest_type=summary_json.get("sections", {}).get("frequency", "weekly"),
                subject=subject,
                html_content=html_content,
                summary_json=summary_json,
                status="generated",
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            logger.error(f"Failed to store digest log for {user_id}: {e}")

    async def _update_last_digest_sent(self, user_id: str) -> None:
        """Update the last_digest_sent_at timestamp for the user."""
        try:
            await self.db.execute(
                sa_update(NotificationPreference)
                .where(NotificationPreference.user_id == user_id)
                .values(
                    last_digest_sent_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db.flush()
        except Exception as e:
            logger.error(f"Failed to update last_digest_sent_at for {user_id}: {e}")

    # ========================================================================
    # Batch Processing
    # ========================================================================

    async def run_digest_batch(self) -> Dict[str, Any]:
        """
        Process all users who are due for a digest.

        Checks each user's notification preferences and generates/sends
        digests for those whose schedule matches today.

        Returns:
            Summary dict with counts of processed, sent, skipped, failed
        """
        logger.info("Starting digest batch processing")
        now = datetime.now(timezone.utc)
        today_weekday = now.strftime("%A").lower()  # e.g., "monday"

        stats = {
            "processed": 0,
            "sent": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        try:
            # Get all users with digest enabled
            prefs_result = await self.db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.digest_frequency != "none"
                )
            )

            all_prefs = prefs_result.scalars().all()
            logger.info(f"Found {len(all_prefs)} users with digests enabled")

            for pref_obj in all_prefs:
                user_id = str(pref_obj.user_id)
                prefs = {
                    "digest_frequency": pref_obj.digest_frequency,
                    "digest_day": pref_obj.digest_day,
                    "last_digest_sent_at": (
                        pref_obj.last_digest_sent_at.isoformat()
                        if pref_obj.last_digest_sent_at
                        else None
                    ),
                    "notification_email": pref_obj.notification_email,
                    "user_id": user_id,
                }
                stats["processed"] += 1

                # Check if this user is due for a digest
                if not self._is_digest_due(prefs, today_weekday, now):
                    stats["skipped"] += 1
                    continue

                try:
                    # Generate the digest
                    result = await self.generate_user_digest(user_id)
                    if not result:
                        stats["skipped"] += 1
                        continue

                    # Get the user's notification email
                    to_email = await self._get_notification_email(user_id, prefs)
                    if not to_email:
                        logger.warning(
                            f"No email configured for user {user_id}, skipping send"
                        )
                        stats["skipped"] += 1
                        continue

                    # Send the email
                    sent = await self.send_digest_email(
                        to_email, result["subject"], result["html_content"]
                    )
                    if sent:
                        stats["sent"] += 1
                        # Update digest log status
                        try:
                            # Find the most recent generated log for this user
                            log_result = await self.db.execute(
                                select(DigestLog)
                                .where(DigestLog.user_id == user_id)
                                .where(DigestLog.status == "generated")
                                .order_by(DigestLog.created_at.desc())
                                .limit(1)
                            )
                            log = log_result.scalar_one_or_none()
                            if log:
                                log.status = "sent"
                                log.sent_at = now
                                await self.db.flush()
                        except Exception:
                            pass
                    else:
                        stats["failed"] += 1

                except Exception as e:
                    logger.error(f"Failed to process digest for user {user_id}: {e}")
                    stats["failed"] += 1
                    stats["errors"].append({"user_id": user_id, "error": str(e)})

        except Exception as e:
            logger.error(f"Digest batch processing failed: {e}")
            stats["errors"].append({"error": str(e)})

        logger.info(
            f"Digest batch complete: {stats['sent']} sent, "
            f"{stats['skipped']} skipped, {stats['failed']} failed "
            f"out of {stats['processed']} processed"
        )
        return stats

    def _is_digest_due(
        self,
        prefs: Dict[str, Any],
        today_weekday: str,
        now: datetime,
    ) -> bool:
        """Check if a user is due for a digest based on their preferences."""
        freq = prefs.get("digest_frequency", "weekly")
        last_sent = prefs.get("last_digest_sent_at")

        if freq == "none":
            return False

        # Parse last_sent timestamp
        last_sent_dt = None
        if last_sent:
            try:
                if isinstance(last_sent, str):
                    last_sent_dt = datetime.fromisoformat(
                        last_sent.replace("Z", "+00:00")
                    )
            except ValueError:
                pass

        if freq == "daily":
            # Due if never sent or last sent > 20 hours ago
            return (now - last_sent_dt) > timedelta(hours=20) if last_sent_dt else True
        elif freq == "weekly":
            # Due if today matches the configured day and not already sent this week
            digest_day = prefs.get("digest_day", "monday")
            if today_weekday != digest_day:
                return False
            return (now - last_sent_dt) > timedelta(days=5) if last_sent_dt else True
        return False

    async def _get_notification_email(
        self, user_id: str, prefs: Dict[str, Any]
    ) -> Optional[str]:
        """
        Get the email address to send the digest to.

        Uses notification_email from preferences if set, otherwise falls
        back to the user's auth email.
        """
        if notification_email := prefs.get("notification_email"):
            return notification_email

        # Fall back to auth email via users table
        try:
            result = await self.db.execute(select(User.email).where(User.id == user_id))
            email = result.scalar()
            return email
        except Exception as e:
            logger.error(f"Failed to get user email for {user_id}: {e}")

        return None
