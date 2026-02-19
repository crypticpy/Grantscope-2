"""Action tools for creating opportunity cards, adding to programs, and creating programs.

These tools perform write operations on the database: creating new
Card records, adding cards to workstreams, and creating new workstreams.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import ToolDefinition, registry
from app.models.db.card import Card
from app.models.db.workstream import Workstream, WorkstreamCard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 8: create_opportunity_card
# ---------------------------------------------------------------------------


async def _handle_create_opportunity_card(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Create a new grant opportunity card in the database.

    Checks for an existing card with a similar name using ILIKE before
    creating a new one.  If a duplicate is found, returns the existing
    card's details instead of creating a new record.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: Card fields (name, summary, grantor, etc.).

    Returns:
        Dict with card_id, slug, name, and created (bool).
    """
    try:
        name: str = kwargs.get("name", "")
        if not name:
            return {"error": "A 'name' is required to create a card."}

        summary: Optional[str] = kwargs.get("summary")
        grantor: Optional[str] = kwargs.get("grantor")
        funding_amount_min: Optional[float] = kwargs.get("funding_amount_min")
        funding_amount_max: Optional[float] = kwargs.get("funding_amount_max")
        deadline_str: Optional[str] = kwargs.get("deadline")
        grant_type: Optional[str] = kwargs.get("grant_type")
        cfda_number: Optional[str] = kwargs.get("cfda_number")
        eligibility_text: Optional[str] = kwargs.get("eligibility_text")
        source_url: Optional[str] = kwargs.get("source_url")

        # Check for existing card with exact name (case-insensitive)
        existing_result = await db.execute(
            select(Card)
            .where(
                func.lower(Card.name) == name.lower(),
                Card.status == "active",
            )
            .limit(1)
        )
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            return {
                "card_id": str(existing.id),
                "slug": existing.slug,
                "name": existing.name,
                "created": False,
                "message": (
                    "A similar grant opportunity already exists in the database."
                ),
            }

        # Generate slug
        slug = name.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())
        slug = slug[:50]
        slug = f"{slug}-{_uuid.uuid4().hex[:8]}"

        # Parse deadline if provided
        deadline_dt: Optional[datetime] = None
        if deadline_str:
            try:
                deadline_dt = datetime.fromisoformat(deadline_str)
                if deadline_dt.tzinfo is None:
                    deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.debug(
                    "Could not parse deadline '%s', storing as None", deadline_str
                )

        now = datetime.now(timezone.utc)

        card_kwargs: Dict[str, Any] = {
            "name": name,
            "slug": slug,
            "summary": summary or "",
            "description": summary or "",
            "status": "active",
            "review_status": "active",
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
        }

        # Set optional grant fields only if provided
        if grantor:
            card_kwargs["grantor"] = grantor
        if funding_amount_min is not None:
            card_kwargs["funding_amount_min"] = funding_amount_min
        if funding_amount_max is not None:
            card_kwargs["funding_amount_max"] = funding_amount_max
        if deadline_dt:
            card_kwargs["deadline"] = deadline_dt
        if grant_type:
            card_kwargs["grant_type"] = grant_type
        if cfda_number:
            card_kwargs["cfda_number"] = cfda_number
        if eligibility_text:
            card_kwargs["eligibility_text"] = eligibility_text
        if source_url:
            card_kwargs["source_url"] = source_url

        # Only set attributes that exist on the Card model
        safe_kwargs = {k: v for k, v in card_kwargs.items() if hasattr(Card, k)}
        card = Card(**safe_kwargs)
        db.add(card)
        await db.flush()
        await db.refresh(card)

        # Queue background AI analysis
        try:
            from app.card_analysis_service import queue_card_analysis

            await queue_card_analysis(db, str(card.id), user_id)
        except Exception:
            logger.warning("Failed to queue card analysis for %s", card.id)

        return {
            "card_id": str(card.id),
            "slug": card.slug,
            "name": card.name,
            "created": True,
            "message": "Grant opportunity card created successfully.",
        }

    except Exception as exc:
        logger.exception("create_opportunity_card failed: %s", exc)
        return {"error": "Failed to create the opportunity card. Please try again."}


registry.register(
    ToolDefinition(
        name="create_opportunity_card",
        description=(
            "Create a new grant opportunity card in the GrantScope database. "
            "Checks for duplicates before creating. Returns the card ID and "
            "slug for the new (or existing) card."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name/title of the grant opportunity.",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the grant opportunity.",
                },
                "grantor": {
                    "type": "string",
                    "description": "Name of the granting organization.",
                },
                "funding_amount_min": {
                    "type": "number",
                    "description": "Minimum funding amount in USD.",
                },
                "funding_amount_max": {
                    "type": "number",
                    "description": "Maximum funding amount in USD.",
                },
                "deadline": {
                    "type": "string",
                    "description": "Application deadline as ISO 8601 date string.",
                },
                "grant_type": {
                    "type": "string",
                    "description": (
                        "Type of grant: federal, state, foundation, "
                        "corporate, or other."
                    ),
                },
                "cfda_number": {
                    "type": "string",
                    "description": "CFDA/Assistance Listing number.",
                },
                "eligibility_text": {
                    "type": "string",
                    "description": "Eligibility criteria text.",
                },
                "source_url": {
                    "type": "string",
                    "description": "URL where the grant was found.",
                },
            },
            "required": ["name"],
        },
        handler=_handle_create_opportunity_card,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 9: add_card_to_program
# ---------------------------------------------------------------------------


async def _handle_add_card_to_program(
    db: AsyncSession, user_id: str, **kwargs: Any
) -> dict:
    """Add a grant card to a user's workstream/program.

    Verifies that both the card and workstream exist, that the user
    owns the workstream, and that the card is not already in the
    workstream before creating the association.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: ``card_id`` (str), ``workstream_id`` (str).

    Returns:
        Dict with success status and message.
    """
    try:
        card_id_str: str = kwargs.get("card_id", "")
        workstream_id_str: str = kwargs.get("workstream_id", "")

        if not card_id_str or not workstream_id_str:
            return {"error": "Both 'card_id' and 'workstream_id' are required."}

        # Validate UUIDs
        try:
            card_uuid = _uuid.UUID(card_id_str)
            workstream_uuid = _uuid.UUID(workstream_id_str)
            user_uuid = _uuid.UUID(user_id)
        except ValueError:
            return {"error": "Invalid UUID format for card_id or workstream_id."}

        # Verify card exists
        card_result = await db.execute(select(Card).where(Card.id == card_uuid))
        card = card_result.scalar_one_or_none()
        if card is None:
            return {"error": "Card not found."}

        # Verify workstream exists and belongs to user
        ws_result = await db.execute(
            select(Workstream).where(
                Workstream.id == workstream_uuid,
                Workstream.user_id == user_uuid,
            )
        )
        workstream = ws_result.scalar_one_or_none()
        if workstream is None:
            return {"error": ("Program not found or you do not have access to it.")}

        # Check for existing association
        dup_result = await db.execute(
            select(WorkstreamCard).where(
                and_(
                    WorkstreamCard.workstream_id == workstream_uuid,
                    WorkstreamCard.card_id == card_uuid,
                )
            )
        )
        if dup_result.scalar_one_or_none() is not None:
            return {
                "success": True,
                "message": (
                    f"'{card.name}' is already in program '{workstream.name}'."
                ),
                "already_existed": True,
            }

        # Create the association
        now = datetime.now(timezone.utc)
        wsc = WorkstreamCard(
            workstream_id=workstream_uuid,
            card_id=card_uuid,
            added_by=user_uuid,
            status="inbox",
            added_from="assistant",
            added_at=now,
            updated_at=now,
        )
        db.add(wsc)
        await db.flush()

        return {
            "success": True,
            "message": (f"Added '{card.name}' to program '{workstream.name}'."),
            "already_existed": False,
        }

    except Exception as exc:
        logger.exception("add_card_to_program failed: %s", exc)
        return {"error": "Failed to add the card to the program. Please try again."}


registry.register(
    ToolDefinition(
        name="add_card_to_program",
        description=(
            "Add a grant opportunity card to one of the user's programs "
            "(workstreams). Verifies ownership and checks for duplicates."
        ),
        parameters={
            "type": "object",
            "properties": {
                "card_id": {
                    "type": "string",
                    "description": "UUID of the card to add.",
                },
                "workstream_id": {
                    "type": "string",
                    "description": "UUID of the target program/workstream.",
                },
            },
            "required": ["card_id", "workstream_id"],
        },
        handler=_handle_add_card_to_program,
        requires_online=False,
    )
)


# ---------------------------------------------------------------------------
# Tool 10: create_program
# ---------------------------------------------------------------------------


async def _handle_create_program(db: AsyncSession, user_id: str, **kwargs: Any) -> dict:
    """Create a new program (workstream) for the user.

    Args:
        db: Async database session.
        user_id: Authenticated user UUID string.
        **kwargs: ``name`` (str), ``description`` (str), ``pillar_ids``
            (list), ``keywords`` (list), ``category_ids`` (list).

    Returns:
        Dict with workstream_id and name.
    """
    try:
        name: str = kwargs.get("name", "")
        if not name:
            return {"error": "A 'name' is required to create a program."}

        description: Optional[str] = kwargs.get("description")
        pillar_ids: Optional[List[str]] = kwargs.get("pillar_ids")
        keywords: Optional[List[str]] = kwargs.get("keywords")
        category_ids: Optional[List[str]] = kwargs.get("category_ids")

        try:
            user_uuid = _uuid.UUID(user_id)
        except ValueError:
            return {"error": "Invalid user ID format."}

        now = datetime.now(timezone.utc)

        ws_kwargs: Dict[str, Any] = {
            "user_id": user_uuid,
            "name": name,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        if description:
            ws_kwargs["description"] = description
        if pillar_ids:
            ws_kwargs["pillar_ids"] = pillar_ids
        if keywords:
            ws_kwargs["keywords"] = keywords
        if category_ids:
            ws_kwargs["category_ids"] = category_ids

        # Only set attributes that exist on the model
        safe_kwargs = {k: v for k, v in ws_kwargs.items() if hasattr(Workstream, k)}
        workstream = Workstream(**safe_kwargs)
        db.add(workstream)
        await db.flush()
        await db.refresh(workstream)

        return {
            "workstream_id": str(workstream.id),
            "name": workstream.name,
            "message": f"Program '{workstream.name}' created successfully.",
        }

    except Exception as exc:
        logger.exception("create_program failed: %s", exc)
        return {"error": "Failed to create the program. Please try again."}


registry.register(
    ToolDefinition(
        name="create_program",
        description=(
            "Create a new grant tracking program (workstream) for the user. "
            "Programs organize grant opportunities by theme, department, or "
            "strategic focus."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new program.",
                },
                "description": {
                    "type": "string",
                    "description": "Description of the program's focus and goals.",
                },
                "pillar_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Strategic pillar IDs to associate " "(e.g. ['CH', 'HS'])."
                    ),
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords for matching opportunities.",
                },
                "category_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grant category IDs to associate.",
                },
            },
            "required": ["name"],
        },
        handler=_handle_create_program,
        requires_online=False,
    )
)
