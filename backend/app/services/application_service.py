"""Business logic for the Application Tracking feature."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.grant_application import GrantApplication
from app.models.db.milestone import ApplicationMilestone, ApplicationStatusHistory
from app.models.db.wizard_session import WizardSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed status transitions
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["in_progress"],
    "in_progress": ["under_review", "submitted", "withdrawn"],
    "under_review": ["in_progress", "submitted"],
    "submitted": ["pending_decision", "withdrawn"],
    "pending_decision": ["awarded", "declined"],
    # Terminal states -- no outgoing transitions
    "awarded": [],
    "declined": [],
    "withdrawn": [],
    "expired": [],
}

PIPELINE_STATUSES = {"in_progress", "under_review", "submitted"}


class ApplicationService:
    """Service layer for grant application operations."""

    # ------------------------------------------------------------------
    # create_from_wizard
    # ------------------------------------------------------------------

    @staticmethod
    async def create_from_wizard(
        db: AsyncSession,
        wizard_session_id: UUID,
        user_id: UUID,
    ) -> GrantApplication:
        """Create a GrantApplication from a completed wizard session.

        Fetches the wizard session, creates the application record, and
        auto-generates standard milestones from the grant context.

        Args:
            db: Async database session.
            wizard_session_id: UUID of the wizard session.
            user_id: UUID of the authenticated user.

        Returns:
            The newly created GrantApplication.

        Raises:
            ValueError: If the wizard session is not found.
        """
        result = await db.execute(
            select(WizardSession).where(WizardSession.id == wizard_session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError("Wizard session not found")

        application = GrantApplication(
            card_id=session.card_id,
            workstream_id=session.workstream_id,
            user_id=user_id,
            status="in_progress",
            proposal_content=session.plan_data or {},
        )
        db.add(application)
        await db.flush()
        await db.refresh(application)

        # Auto-create milestones from grant context
        grant_context = session.grant_context or {}
        if grant_context:
            await ApplicationService.auto_create_milestones(
                db, application.id, grant_context
            )

        return application

    # ------------------------------------------------------------------
    # update_status
    # ------------------------------------------------------------------

    @staticmethod
    async def update_status(
        db: AsyncSession,
        application_id: UUID,
        new_status: str,
        changed_by: UUID,
        reason: str | None = None,
    ) -> GrantApplication:
        """Update application status with transition validation and history.

        Args:
            db: Async database session.
            application_id: UUID of the application.
            new_status: Target status value.
            changed_by: UUID of the user making the change.
            reason: Optional reason for the status change.

        Returns:
            The updated GrantApplication.

        Raises:
            ValueError: If the application is not found or the transition
                is invalid.
        """
        result = await db.execute(
            select(GrantApplication).where(GrantApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise ValueError("Application not found")

        old_status = application.status or "draft"
        allowed = ALLOWED_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{old_status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(allowed) if allowed else 'none (terminal state)'}"
            )

        # Record history
        history = ApplicationStatusHistory(
            application_id=application_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
        db.add(history)

        # Update application
        application.status = new_status
        now = datetime.now(timezone.utc)
        application.updated_at = now

        if new_status == "submitted":
            application.submitted_at = now
        elif new_status in ("awarded", "declined"):
            application.decision_at = now

        await db.flush()
        await db.refresh(application)
        return application

    # ------------------------------------------------------------------
    # get_dashboard
    # ------------------------------------------------------------------

    @staticmethod
    async def get_dashboard(db: AsyncSession, user_id: UUID) -> dict:
        """Build aggregated dashboard stats for a user's applications.

        Args:
            db: Async database session.
            user_id: UUID of the authenticated user.

        Returns:
            Dict with ``stats`` (DashboardStats-compatible) and
            ``recent_applications`` (list of enriched dicts).
        """
        # --- Counts by status ---
        status_counts_result = await db.execute(
            select(
                GrantApplication.status,
                func.count(GrantApplication.id),
            )
            .where(GrantApplication.user_id == user_id)
            .group_by(GrantApplication.status)
        )
        by_status: dict[str, int] = {}
        total = 0
        for row in status_counts_result.all():
            count = row[1]
            by_status[row[0] or "draft"] = count
            total += count

        submitted_count = by_status.get("submitted", 0) + by_status.get(
            "pending_decision", 0
        )
        awarded_count = by_status.get("awarded", 0)

        # --- Pipeline value (sum of funding_amount_max for pipeline statuses) ---
        pipeline_value_result = await db.execute(
            select(func.coalesce(func.sum(Card.funding_amount_max), 0))
            .select_from(GrantApplication)
            .join(Card, Card.id == GrantApplication.card_id)
            .where(
                GrantApplication.user_id == user_id,
                GrantApplication.status.in_(list(PIPELINE_STATUSES)),
            )
        )
        total_pipeline_value = float(pipeline_value_result.scalar() or 0)

        # --- Upcoming deadlines (milestones due within 30 days, not completed) ---
        deadline_cutoff = datetime.now(timezone.utc) + timedelta(days=30)
        upcoming_result = await db.execute(
            select(func.count(ApplicationMilestone.id))
            .select_from(ApplicationMilestone)
            .join(
                GrantApplication,
                GrantApplication.id == ApplicationMilestone.application_id,
            )
            .where(
                GrantApplication.user_id == user_id,
                ApplicationMilestone.is_completed.is_(False),
                ApplicationMilestone.due_date.isnot(None),
                ApplicationMilestone.due_date <= deadline_cutoff,
            )
        )
        upcoming_deadlines = upcoming_result.scalar() or 0

        # --- Recent 10 applications with card details ---
        recent_apps = await ApplicationService._list_applications_with_details(
            db, user_id, limit=10, offset=0
        )

        return {
            "stats": {
                "total_applications": total,
                "by_status": by_status,
                "total_pipeline_value": total_pipeline_value,
                "submitted_count": submitted_count,
                "awarded_count": awarded_count,
                "upcoming_deadlines": upcoming_deadlines,
            },
            "recent_applications": recent_apps,
        }

    # ------------------------------------------------------------------
    # auto_create_milestones
    # ------------------------------------------------------------------

    @staticmethod
    async def auto_create_milestones(
        db: AsyncSession,
        application_id: UUID,
        grant_context: dict,
    ) -> list[ApplicationMilestone]:
        """Parse grant_context and create standard milestones.

        Looks for ``deadline`` (ISO string) and ``key_dates`` (list of
        dicts with ``title``, ``date``, ``type``) in the grant context.
        Always adds internal draft review (14 days before deadline) and
        final review (7 days before deadline) when a deadline is present.

        Args:
            db: Async database session.
            application_id: UUID of the grant application.
            grant_context: Dict from the wizard session.

        Returns:
            List of created ApplicationMilestone rows.
        """
        created: list[ApplicationMilestone] = []
        sort_order = 0
        deadline_dt: datetime | None = None

        # Parse main deadline
        raw_deadline = grant_context.get("deadline")
        if raw_deadline:
            try:
                if isinstance(raw_deadline, str):
                    deadline_dt = datetime.fromisoformat(
                        raw_deadline.replace("Z", "+00:00")
                    )
                elif isinstance(raw_deadline, datetime):
                    deadline_dt = raw_deadline
            except (ValueError, TypeError):
                logger.warning(
                    "Could not parse deadline from grant_context: %s", raw_deadline
                )

        # Internal draft review (14 days before deadline)
        if deadline_dt:
            draft_review_date = deadline_dt - timedelta(days=14)
            draft_ms = ApplicationMilestone(
                application_id=application_id,
                title="Internal draft review",
                description="Complete internal review of draft application",
                due_date=draft_review_date,
                milestone_type="draft_review",
                sort_order=sort_order,
            )
            db.add(draft_ms)
            created.append(draft_ms)
            sort_order += 1

        # Final review (7 days before deadline)
        if deadline_dt:
            final_review_date = deadline_dt - timedelta(days=7)
            final_ms = ApplicationMilestone(
                application_id=application_id,
                title="Final review",
                description="Final review and sign-off before submission",
                due_date=final_review_date,
                milestone_type="internal_review",
                sort_order=sort_order,
            )
            db.add(final_ms)
            created.append(final_ms)
            sort_order += 1

        # Key dates from grant context
        key_dates = grant_context.get("key_dates", [])
        if isinstance(key_dates, list):
            for entry in key_dates:
                if not isinstance(entry, dict):
                    continue
                title = entry.get("title", "Key date")
                raw_date = entry.get("date")
                ms_type = entry.get("type", "custom")
                due = None
                if raw_date:
                    try:
                        if isinstance(raw_date, str):
                            due = datetime.fromisoformat(
                                raw_date.replace("Z", "+00:00")
                            )
                        elif isinstance(raw_date, datetime):
                            due = raw_date
                    except (ValueError, TypeError):
                        pass
                ms = ApplicationMilestone(
                    application_id=application_id,
                    title=title,
                    description=entry.get("description"),
                    due_date=due,
                    milestone_type=ms_type,
                    sort_order=sort_order,
                )
                db.add(ms)
                created.append(ms)
                sort_order += 1

        # Submission deadline milestone
        if deadline_dt:
            submission_ms = ApplicationMilestone(
                application_id=application_id,
                title="Submission deadline",
                description="Grant application submission deadline",
                due_date=deadline_dt,
                milestone_type="submission",
                sort_order=sort_order,
            )
            db.add(submission_ms)
            created.append(submission_ms)
            sort_order += 1

        if created:
            await db.flush()
            for ms in created:
                await db.refresh(ms)

        return created

    # ------------------------------------------------------------------
    # get_application_with_details
    # ------------------------------------------------------------------

    @staticmethod
    async def get_application_with_details(
        db: AsyncSession,
        application_id: UUID,
    ) -> dict:
        """Fetch a single application with card info and milestone summary.

        Args:
            db: Async database session.
            application_id: UUID of the application.

        Returns:
            Dict suitable for ApplicationWithDetails serialisation.

        Raises:
            ValueError: If the application is not found.
        """
        result = await db.execute(
            select(
                GrantApplication,
                Card.name,
                Card.grantor,
                Card.funding_amount_max,
                Card.deadline,
            )
            .outerjoin(Card, Card.id == GrantApplication.card_id)
            .where(GrantApplication.id == application_id)
        )
        row = result.one_or_none()
        if row is None:
            raise ValueError("Application not found")

        app, card_title, grantor_name, funding_max, card_deadline = row

        # Milestone summary
        milestone_result = await db.execute(
            select(
                func.count(ApplicationMilestone.id),
                func.sum(
                    case((ApplicationMilestone.is_completed.is_(True), 1), else_=0)
                ),
            ).where(ApplicationMilestone.application_id == application_id)
        )
        ms_row = milestone_result.one()
        milestone_count = ms_row[0] or 0
        completed_milestones = int(ms_row[1] or 0)
        progress_pct = (
            round(completed_milestones / milestone_count * 100, 1)
            if milestone_count > 0
            else 0.0
        )

        return {
            "id": str(app.id),
            "card_id": str(app.card_id),
            "workstream_id": str(app.workstream_id),
            "department_id": app.department_id,
            "user_id": str(app.user_id),
            "status": app.status,
            "proposal_content": app.proposal_content,
            "awarded_amount": float(app.awarded_amount) if app.awarded_amount else None,
            "submitted_at": app.submitted_at,
            "decision_at": app.decision_at,
            "notes": app.notes,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
            "card_title": card_title,
            "grantor_name": grantor_name,
            "funding_amount_max": float(funding_max) if funding_max else None,
            "deadline": card_deadline.isoformat() if card_deadline else None,
            "milestone_count": milestone_count,
            "completed_milestones": completed_milestones,
            "progress_pct": progress_pct,
        }

    # ------------------------------------------------------------------
    # Internal: list applications with details
    # ------------------------------------------------------------------

    @staticmethod
    async def _list_applications_with_details(
        db: AsyncSession,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
        status_filter: str | None = None,
        sort_by: str = "created_at",
    ) -> list[dict]:
        """Fetch user applications with card details and milestone progress.

        Args:
            db: Async database session.
            user_id: UUID of the user.
            limit: Max rows to return.
            offset: Number of rows to skip.
            status_filter: Optional status value to filter by.
            sort_by: Column to sort by (created_at, deadline, status).

        Returns:
            List of dicts suitable for ApplicationWithDetails serialisation.
        """
        # Build milestone sub-query
        ms_total = (
            select(func.count(ApplicationMilestone.id))
            .where(ApplicationMilestone.application_id == GrantApplication.id)
            .correlate(GrantApplication)
            .scalar_subquery()
        )
        ms_completed = (
            select(
                func.sum(
                    case((ApplicationMilestone.is_completed.is_(True), 1), else_=0)
                )
            )
            .where(ApplicationMilestone.application_id == GrantApplication.id)
            .correlate(GrantApplication)
            .scalar_subquery()
        )

        query = (
            select(
                GrantApplication,
                Card.name.label("card_title"),
                Card.grantor.label("grantor_name"),
                Card.funding_amount_max,
                Card.deadline.label("card_deadline"),
                ms_total.label("milestone_count"),
                ms_completed.label("completed_milestones"),
            )
            .outerjoin(Card, Card.id == GrantApplication.card_id)
            .where(GrantApplication.user_id == user_id)
        )

        if status_filter:
            query = query.where(GrantApplication.status == status_filter)

        # Sorting
        if sort_by == "deadline":
            query = query.order_by(Card.deadline.asc().nulls_last())
        elif sort_by == "status":
            query = query.order_by(GrantApplication.status.asc())
        else:
            query = query.order_by(GrantApplication.created_at.desc())

        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        rows = result.all()

        applications: list[dict] = []
        for row in rows:
            app = row[0]
            card_title = row[1]
            grantor_name = row[2]
            funding_max = row[3]
            card_deadline = row[4]
            ms_count = row[5] or 0
            ms_done = int(row[6] or 0)
            progress = round(ms_done / ms_count * 100, 1) if ms_count > 0 else 0.0
            applications.append(
                {
                    "id": str(app.id),
                    "card_id": str(app.card_id),
                    "workstream_id": str(app.workstream_id),
                    "department_id": app.department_id,
                    "user_id": str(app.user_id),
                    "status": app.status,
                    "proposal_content": app.proposal_content,
                    "awarded_amount": (
                        float(app.awarded_amount) if app.awarded_amount else None
                    ),
                    "submitted_at": app.submitted_at,
                    "decision_at": app.decision_at,
                    "notes": app.notes,
                    "created_at": app.created_at,
                    "updated_at": app.updated_at,
                    "card_title": card_title,
                    "grantor_name": grantor_name,
                    "funding_amount_max": (float(funding_max) if funding_max else None),
                    "deadline": (card_deadline.isoformat() if card_deadline else None),
                    "milestone_count": ms_count,
                    "completed_milestones": ms_done,
                    "progress_pct": progress,
                }
            )

        return applications
