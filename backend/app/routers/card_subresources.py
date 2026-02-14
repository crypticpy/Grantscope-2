"""Card sub-resource router -- sources, timeline, history, related, follow, notes, assets, velocity."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.deps import supabase, get_current_user, _safe_error
from app.models.core import Card
from app.models.history import (
    ScoreHistory,
    ScoreHistoryResponse,
    StageHistory,
    StageHistoryList,
    RelatedCard,
    RelatedCardsList,
)
from app.models.workstream import Note, NoteCreate
from app.models.assets import CardAsset, CardAssetsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["card-subresources"])


# ============================================================================
# Entity models
# ============================================================================


class EntityItem(BaseModel):
    id: str
    name: str
    entity_type: str
    context: Optional[str] = None
    source_id: Optional[str] = None
    canonical_name: Optional[str] = None
    created_at: str


class EntityListResponse(BaseModel):
    entities: List[EntityItem]
    total_count: int
    card_id: str


# ============================================================================
# Card relationships / sources / timeline
# ============================================================================


@router.get("/cards/{card_id}/sources")
async def get_card_sources(card_id: str):
    """Get sources for a card"""
    response = (
        supabase.table("sources")
        .select("*")
        .eq("card_id", card_id)
        .order("relevance_score", desc=True)
        .execute()
    )
    return response.data


@router.get("/cards/{card_id}/timeline")
async def get_card_timeline(card_id: str):
    """Get timeline for a card"""
    response = (
        supabase.table("card_timeline")
        .select("*")
        .eq("card_id", card_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@router.get("/cards/{card_id}/entities", response_model=EntityListResponse)
async def get_card_entities(
    card_id: str,
    entity_type: Optional[str] = None,
    limit: int = 50,
):
    """
    Get entities extracted from a card's sources.

    Returns entities (technologies, organizations, concepts, people, locations)
    associated with the given card, optionally filtered by entity type.

    Args:
        card_id: UUID of the card to get entities for
        entity_type: Optional filter by entity type (technology, organization,
                     concept, person, location)
        limit: Maximum number of entities to return (default: 50)

    Returns:
        EntityListResponse with list of entities and metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Build query for entities
    query = (
        supabase.table("entities")
        .select("id, name, entity_type, context, source_id, canonical_name, created_at")
        .eq("card_id", card_id)
    )

    # Apply optional entity_type filter
    if entity_type:
        query = query.eq("entity_type", entity_type)

    # Execute query ordered by name, with limit
    response = query.order("name").limit(limit).execute()

    # Convert to EntityItem models
    entities = (
        [EntityItem(**record) for record in response.data] if response.data else []
    )

    return EntityListResponse(
        entities=entities,
        total_count=len(entities),
        card_id=card_id,
    )


@router.get("/cards/{card_id}/score-history", response_model=ScoreHistoryResponse)
async def get_card_score_history(
    card_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Get historical score data for a card to enable trend visualization.

    Returns a list of score snapshots ordered by recorded_at (most recent first),
    containing all 7 score dimensions (maturity, velocity, novelty, impact,
    relevance, risk, opportunity) for each timestamp.

    Args:
        card_id: UUID of the card to get score history for
        start_date: Optional filter to get records from this date onwards
        end_date: Optional filter to get records up to this date

    Returns:
        ScoreHistoryResponse with list of ScoreHistory records and metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Build query for score history
    query = supabase.table("card_score_history").select("*").eq("card_id", card_id)

    # Apply date filters if provided
    if start_date:
        query = query.gte("recorded_at", start_date.isoformat())
    if end_date:
        query = query.lte("recorded_at", end_date.isoformat())

    # Execute query ordered by recorded_at descending
    response = query.order("recorded_at", desc=True).execute()

    # Convert to ScoreHistory models
    history_records = (
        [ScoreHistory(**record) for record in response.data] if response.data else []
    )

    return ScoreHistoryResponse(
        history=history_records,
        card_id=card_id,
        total_count=len(history_records),
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/cards/{card_id}/stage-history", response_model=StageHistoryList)
async def get_card_stage_history(
    card_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Get maturity stage transition history for a card.

    Returns a list of stage transitions ordered by changed_at (most recent first),
    tracking maturity stage progression through stages 1-8 and horizon shifts
    (H3 -> H2 -> H1).

    The data is sourced from the card_timeline table, filtered to only include
    'stage_changed' event types.

    Args:
        card_id: UUID of the card to get stage history for

    Returns:
        StageHistoryList with stage transition records and metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Query card_timeline for stage change events
    # Filter by event_type='stage_changed' to get only stage transitions
    response = (
        supabase.table("card_timeline")
        .select(
            "id, card_id, created_at, old_stage_id, new_stage_id, old_horizon, new_horizon, trigger, reason"
        )
        .eq("card_id", card_id)
        .eq("event_type", "stage_changed")
        .order("created_at", desc=True)
        .execute()
    )

    # Convert to StageHistory models, mapping created_at to changed_at
    history_records = []
    if response.data:
        history_records.extend(
            StageHistory(
                id=record["id"],
                card_id=record["card_id"],
                changed_at=record["created_at"],  # Map created_at to changed_at
                old_stage_id=record.get("old_stage_id"),
                new_stage_id=record["new_stage_id"],
                old_horizon=record.get("old_horizon"),
                new_horizon=record.get("new_horizon", "H3"),  # Default to H3 if not set
                trigger=record.get("trigger"),
                reason=record.get("reason"),
            )
            for record in response.data
            if record.get("new_stage_id") is not None
        )
    return StageHistoryList(
        history=history_records, total_count=len(history_records), card_id=card_id
    )


@router.get("/cards/{card_id}/related", response_model=RelatedCardsList)
async def get_related_cards(
    card_id: str, limit: int = 20, current_user: dict = Depends(get_current_user)
):
    """
    Get cards related to the specified card for concept network visualization.

    Returns cards connected to the source card through the card_relationships table,
    including relationship metadata (type and strength) for edge visualization.
    Relationships are bidirectional - cards appear whether they are source or target.

    Args:
        card_id: UUID of the source card to get relationships for
        limit: Maximum number of related cards to return (default: 20)

    Returns:
        RelatedCardsList with related card details and relationship metadata
    """
    # First verify the card exists
    card_response = supabase.table("cards").select("id").eq("id", card_id).execute()
    if not card_response.data:
        raise HTTPException(status_code=404, detail="Card not found")

    # Query relationships where this card is either source or target
    # Get relationships where card is the source
    source_response = (
        supabase.table("card_relationships")
        .select(
            "id, source_card_id, target_card_id, relationship_type, strength, created_at"
        )
        .eq("source_card_id", card_id)
        .limit(limit)
        .execute()
    )

    # Get relationships where card is the target
    target_response = (
        supabase.table("card_relationships")
        .select(
            "id, source_card_id, target_card_id, relationship_type, strength, created_at"
        )
        .eq("target_card_id", card_id)
        .limit(limit)
        .execute()
    )

    # Combine and deduplicate relationships
    all_relationships = []
    seen_relationship_ids = set()

    for rel in (source_response.data or []) + (target_response.data or []):
        if rel["id"] not in seen_relationship_ids:
            seen_relationship_ids.add(rel["id"])
            all_relationships.append(rel)

    # If no relationships found, return empty list
    if not all_relationships:
        return RelatedCardsList(related_cards=[], total_count=0, source_card_id=card_id)

    # Get the related card IDs (the "other" card in each relationship)
    related_card_ids = set()
    for rel in all_relationships:
        if rel["source_card_id"] == card_id:
            related_card_ids.add(rel["target_card_id"])
        else:
            related_card_ids.add(rel["source_card_id"])

    # Fetch full card details for all related cards
    cards_response = (
        supabase.table("cards")
        .select("id, name, slug, summary, pillar_id, stage_id, horizon")
        .in_("id", list(related_card_ids))
        .execute()
    )

    # Create a lookup map for cards
    cards_map = {card["id"]: card for card in (cards_response.data or [])}

    # Build the related cards list with relationship context
    related_cards = []
    for rel in all_relationships:
        # Determine which card is the "related" one (not the source card_id)
        if rel["source_card_id"] == card_id:
            related_id = rel["target_card_id"]
        else:
            related_id = rel["source_card_id"]

        if card_data := cards_map.get(related_id):
            related_cards.append(
                RelatedCard(
                    id=card_data["id"],
                    name=card_data["name"],
                    slug=card_data["slug"],
                    summary=card_data.get("summary"),
                    pillar_id=card_data.get("pillar_id"),
                    stage_id=card_data.get("stage_id"),
                    horizon=card_data.get("horizon"),
                    relationship_type=rel["relationship_type"],
                    relationship_strength=rel.get("strength"),
                    relationship_id=rel["id"],
                )
            )

    # Limit the results to the specified limit
    related_cards = related_cards[:limit]

    return RelatedCardsList(
        related_cards=related_cards,
        total_count=len(related_cards),
        source_card_id=card_id,
    )


# ============================================================================
# Follow / unfollow
# ============================================================================


@router.post("/cards/{card_id}/follow")
async def follow_card(card_id: str, current_user: dict = Depends(get_current_user)):
    """Follow a card"""
    response = (
        supabase.table("card_follows")
        .insert({"user_id": current_user["id"], "card_id": card_id})
        .execute()
    )
    try:
        from app.signal_quality import update_signal_quality_score

        update_signal_quality_score(supabase, card_id)
    except Exception as e:
        logger.warning(f"Failed to update signal quality score for {card_id}: {e}")
    return {"status": "followed"}


@router.delete("/cards/{card_id}/follow")
async def unfollow_card(card_id: str, current_user: dict = Depends(get_current_user)):
    """Unfollow a card"""
    response = (
        supabase.table("card_follows")
        .delete()
        .eq("user_id", current_user["id"])
        .eq("card_id", card_id)
        .execute()
    )
    try:
        from app.signal_quality import update_signal_quality_score

        update_signal_quality_score(supabase, card_id)
    except Exception as e:
        logger.warning(f"Failed to update signal quality score for {card_id}: {e}")
    return {"status": "unfollowed"}


# ============================================================================
# Following / My Signals
# ============================================================================


@router.get("/me/following")
async def get_following_cards(current_user: dict = Depends(get_current_user)):
    """Get cards followed by current user"""
    response = (
        supabase.table("card_follows")
        .select(
            """
        *,
        cards!inner(*)
    """
        )
        .eq("user_id", current_user["id"])
        .execute()
    )
    return response.data


@router.get("/me/signals")
async def get_my_signals(
    group_by: Optional[str] = Query(
        None, description="Group by: pillar, horizon, workstream"
    ),
    sort_by: str = Query(
        "updated", description="Sort: updated, followed, quality, name"
    ),
    search: Optional[str] = Query(None, description="Search term"),
    pillar: Optional[str] = Query(None, description="Filter by pillar"),
    horizon: Optional[str] = Query(None, description="Filter by horizon"),
    source: Optional[str] = Query(
        None, description="Filter by: followed, created, workstream"
    ),
    quality_min: Optional[int] = Query(None, ge=0, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Get user's personal intelligence hub: followed, created, and workstream signals."""
    user_id = current_user["id"]

    # 1. Get followed card IDs
    follows_resp = (
        supabase.table("card_follows")
        .select("card_id, created_at, priority, notes")
        .eq("user_id", user_id)
        .execute()
    )
    followed_map = {f["card_id"]: f for f in (follows_resp.data or [])}
    followed_ids = list(followed_map.keys())

    # 2. Get user-created card IDs
    created_resp = (
        supabase.table("cards")
        .select("id")
        .eq("created_by", user_id)
        .eq("status", "active")
        .execute()
    )
    created_ids = [c["id"] for c in (created_resp.data or [])]

    # 3. Get cards in user's workstreams
    ws_resp = (
        supabase.table("workstreams")
        .select("id, name")
        .eq("user_id", user_id)
        .execute()
    )
    workstreams = ws_resp.data or []
    ws_ids = [ws["id"] for ws in workstreams]
    ws_card_ids = []
    ws_card_map: Dict[str, List[str]] = {}  # card_id -> list of workstream names
    if ws_ids:
        wc_resp = (
            supabase.table("workstream_cards")
            .select("card_id, workstream_id")
            .in_("workstream_id", ws_ids)
            .execute()
        )
        ws_name_map = {ws["id"]: ws["name"] for ws in workstreams}
        for wc in wc_resp.data or []:
            cid = wc["card_id"]
            ws_card_ids.append(cid)
            if cid not in ws_card_map:
                ws_card_map[cid] = []
            ws_card_map[cid].append(ws_name_map.get(wc["workstream_id"], "Unknown"))

    # 4. Union unique card IDs, applying source filter if specified
    if source == "followed":
        all_ids = list(set(followed_ids))
    elif source == "created":
        all_ids = list(set(created_ids))
    elif source == "workstream":
        all_ids = list(set(ws_card_ids))
    else:
        all_ids = list(set(followed_ids + created_ids + ws_card_ids))

    if not all_ids:
        return {
            "signals": [],
            "stats": {
                "total": 0,
                "followed_count": 0,
                "created_count": 0,
                "workstream_count": len(workstreams),
                "updates_this_week": 0,
                "needs_research": 0,
            },
            "workstreams": workstreams,
        }

    # 5. Fetch full card data for all IDs
    cards_query = (
        supabase.table("cards").select("*").in_("id", all_ids).eq("status", "active")
    )

    if search:
        safe_search = re.sub(r"[,.()\[\]]", "", search)
        cards_query = cards_query.or_(
            f"name.ilike.%{safe_search}%,summary.ilike.%{safe_search}%"
        )
    if pillar:
        cards_query = cards_query.eq("pillar_id", pillar)
    if horizon:
        cards_query = cards_query.eq("horizon", horizon)
    if quality_min is not None and quality_min > 0:
        cards_query = cards_query.gte("signal_quality_score", quality_min)

    cards_resp = cards_query.execute()
    cards = cards_resp.data or []

    # 6. Get user signal preferences (pins) -- gracefully degrade if table missing
    try:
        prefs_resp = (
            supabase.table("user_signal_preferences")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        prefs_map = {p["card_id"]: p for p in (prefs_resp.data or [])}
    except Exception:
        logger.warning("user_signal_preferences table may not exist; skipping pin data")
        prefs_map = {}

    # 7. Enrich cards with personal metadata
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    enriched = []
    for card in cards:
        cid = card["id"]
        pref = prefs_map.get(cid, {})
        follow_data = followed_map.get(cid)
        enriched.append(
            {
                **card,
                "is_followed": cid in followed_ids,
                "is_created": cid in created_ids,
                "is_pinned": pref.get("is_pinned", False),
                "personal_notes": pref.get("notes"),
                "follow_priority": follow_data.get("priority") if follow_data else None,
                "followed_at": follow_data.get("created_at") if follow_data else None,
                "workstream_names": ws_card_map.get(cid, []),
            }
        )

    # 8. Sort
    if sort_by == "quality":
        enriched.sort(key=lambda c: c.get("signal_quality_score") or 0, reverse=True)
    elif sort_by == "followed":
        enriched.sort(key=lambda c: c.get("followed_at") or "", reverse=True)
    elif sort_by == "name":
        enriched.sort(key=lambda c: c.get("name", "").lower())
    else:  # default: updated
        enriched.sort(
            key=lambda c: c.get("updated_at") or c.get("created_at") or "", reverse=True
        )

    # Pinned first
    enriched.sort(key=lambda c: 0 if c.get("is_pinned") else 1)

    # 9. Stats
    updates_this_week = sum(
        bool((c.get("updated_at") or "") >= one_week_ago) for c in enriched
    )
    needs_research = sum(
        bool((c.get("signal_quality_score") or 0) < 30) for c in enriched
    )

    return {
        "signals": enriched,
        "stats": {
            "total": len(enriched),
            "followed_count": sum(bool(c.get("is_followed")) for c in enriched),
            "created_count": sum(bool(c.get("is_created")) for c in enriched),
            "workstream_count": len(workstreams),
            "updates_this_week": updates_this_week,
            "needs_research": needs_research,
        },
        "workstreams": workstreams,
    }


# ============================================================================
# Pin signal
# ============================================================================


@router.post("/me/signals/{card_id}/pin")
async def pin_signal(card_id: str, current_user: dict = Depends(get_current_user)):
    """Pin/unpin a signal in the user's personal hub."""
    user_id = current_user["id"]

    # Check if preference exists
    existing = (
        supabase.table("user_signal_preferences")
        .select("id, is_pinned")
        .eq("user_id", user_id)
        .eq("card_id", card_id)
        .execute()
    )

    if existing.data:
        # Toggle pin
        new_val = not existing.data[0].get("is_pinned", False)
        supabase.table("user_signal_preferences").update(
            {"is_pinned": new_val, "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", existing.data[0]["id"]).execute()
        return {"is_pinned": new_val}
    else:
        # Create with pinned=True
        supabase.table("user_signal_preferences").insert(
            {
                "user_id": user_id,
                "card_id": card_id,
                "is_pinned": True,
            }
        ).execute()
        return {"is_pinned": True}


# ============================================================================
# Notes
# ============================================================================


@router.get("/cards/{card_id}/notes")
async def get_card_notes(card_id: str, current_user: dict = Depends(get_current_user)):
    """Get notes for a card"""
    response = (
        supabase.table("card_notes")
        .select("*")
        .eq("card_id", card_id)
        .or_(f"user_id.eq.{current_user['id']},is_private.eq.false")
        .order("created_at", desc=True)
        .execute()
    )
    return [Note(**note) for note in response.data]


@router.post("/cards/{card_id}/notes")
async def create_note(
    card_id: str, note_data: NoteCreate, current_user: dict = Depends(get_current_user)
):
    """Create note for a card"""
    note_dict = note_data.dict()
    note_dict.update(
        {
            "user_id": current_user["id"],
            "card_id": card_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    response = supabase.table("card_notes").insert(note_dict).execute()
    if response.data:
        return Note(**response.data[0])
    else:
        raise HTTPException(status_code=400, detail="Failed to create note")


# ============================================================================
# Assets
# ============================================================================


@router.get("/cards/{card_id}/assets", response_model=CardAssetsResponse)
async def get_card_assets(card_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get all generated assets for a card.

    Returns a list of all briefs, research reports, and exports
    associated with the card across all workstreams.

    Args:
        card_id: UUID of the card
        current_user: Authenticated user (injected)

    Returns:
        CardAssetsResponse with list of assets

    Raises:
        HTTPException 404: Card not found
    """
    try:
        # Verify card exists
        card_response = (
            supabase.table("cards").select("id, name").eq("id", card_id).execute()
        )
        if not card_response.data:
            raise HTTPException(status_code=404, detail="Card not found")

        card_name = card_response.data[0].get("name", "Unknown Card")
        assets = []

        # 1. Fetch executive briefs for this card
        briefs_response = (
            supabase.table("executive_briefs")
            .select(
                "id, version, status, summary, generated_at, model_used, created_at"
            )
            .eq("card_id", card_id)
            .order("created_at", desc=True)
            .execute()
        )

        for brief in briefs_response.data or []:
            # Map status
            brief_status = (
                "ready"
                if brief.get("status") == "completed"
                else brief.get("status", "ready")
            )
            if brief_status == "generating":
                brief_status = "generating"
            elif brief_status in ("pending", "failed"):
                brief_status = "failed" if brief_status == "failed" else "ready"

            title = f"Executive Brief v{brief.get('version', 1)}"
            if brief.get("summary"):
                # Truncate summary for title if needed
                summary_preview = (
                    brief["summary"][:50] + "..."
                    if len(brief.get("summary", "")) > 50
                    else brief.get("summary", "")
                )
                title = f"Executive Brief v{brief.get('version', 1)}"

            assets.append(
                CardAsset(
                    id=brief["id"],
                    type="brief",
                    title=title,
                    created_at=brief.get("generated_at") or brief.get("created_at"),
                    version=brief.get("version", 1),
                    ai_generated=True,
                    ai_model=brief.get("model_used"),
                    status=brief_status,
                    metadata={
                        "summary_preview": (
                            brief.get("summary", "")[:200]
                            if brief.get("summary")
                            else None
                        )
                    },
                )
            )

        # 2. Fetch research tasks (deep research reports)
        research_response = (
            supabase.table("research_tasks")
            .select("id, task_type, status, result_summary, completed_at, created_at")
            .eq("card_id", card_id)
            .order("created_at", desc=True)
            .execute()
        )

        for task in research_response.data or []:
            # Only include completed or failed tasks as assets
            if task.get("status") not in ("completed", "failed"):
                continue

            task_type = task.get("task_type", "research")
            asset_type = "research"
            if task_type == "deep_research":
                title = "Strategic Intelligence Report"
            elif task_type == "update":
                title = "Quick Update Report"
            else:
                title = f"{task_type.replace('_', ' ').title()} Report"

            result = task.get("result_summary", {}) or {}

            assets.append(
                CardAsset(
                    id=task["id"],
                    type=asset_type,
                    title=title,
                    created_at=task.get("completed_at") or task.get("created_at"),
                    ai_generated=True,
                    status="ready" if task.get("status") == "completed" else "failed",
                    metadata={
                        "task_type": task_type,
                        "sources_found": result.get("sources_found"),
                        "sources_added": result.get("sources_added"),
                    },
                )
            )

        # Sort all assets by created_at descending
        assets.sort(key=lambda x: x.created_at or "", reverse=True)

        return CardAssetsResponse(
            card_id=card_id, assets=assets, total_count=len(assets)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching card assets: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("card assets retrieval", e),
        ) from e


# ============================================================================
# Velocity
# ============================================================================


@router.get("/cards/{card_id}/velocity")
async def get_card_velocity(
    card_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get velocity trend summary for a specific card."""
    from app.velocity_service import get_velocity_summary

    summary = get_velocity_summary(card_id, supabase)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found or velocity data unavailable.",
        )
    return summary
