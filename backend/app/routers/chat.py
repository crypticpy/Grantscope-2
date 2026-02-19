"""Chat (Ask GrantScope) router -- SQLAlchemy 2.0 async."""

import json
import logging
import os
import uuid
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.deps import get_db, get_current_user_hardcoded, _safe_error
from app.models.chat import ChatRequest, ConversationUpdateRequest
from app.models.db.chat import ChatConversation, ChatMessage, ChatPinnedMessage
from app.models.db.card import Card
from app.models.db.card_extras import CardFollow
from app.models.db.workstream import Workstream
from app.export_service import ExportService
from app.chat_service import (
    chat as chat_service_chat,
    generate_suggestions as chat_generate_suggestions,
)
from app.chat.suggestions import generate_smart_suggestions

# azure_openai_async_client and get_chat_mini_deployment moved to app.chat.suggestions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_dict(obj, skip_cols=None) -> dict:
    """Convert an ORM row to a plain dict, serialising UUID/datetime/Decimal."""
    skip = skip_cols or set()
    result = {}
    for col in obj.__table__.columns:
        if col.name in skip:
            continue
        value = getattr(obj, col.key, None)
        if isinstance(value, uuid.UUID):
            result[col.name] = str(value)
        elif isinstance(value, (datetime, date)):
            result[col.name] = value.isoformat()
        elif isinstance(value, Decimal):
            result[col.name] = float(value)
        else:
            result[col.name] = value
    return result


# ---------------------------------------------------------------------------
# GET /chat/stats
# ---------------------------------------------------------------------------


@router.get("/chat/stats")
async def chat_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get lightweight stats for the chat empty state.
    Returns facts about the user's intelligence data.
    """
    user_id = current_user["id"]
    try:
        facts = []

        # Count followed signals (card_follows, NOT user_follows)
        try:
            result = await db.execute(
                select(func.count(CardFollow.id)).where(CardFollow.user_id == user_id)
            )
            follow_count = result.scalar() or 0
            if follow_count > 0:
                facts.append(
                    f"You're tracking {follow_count} signal{'s' if follow_count != 1 else ''}"
                )
        except Exception:
            pass

        # Count workstreams
        try:
            result = await db.execute(
                select(func.count(Workstream.id)).where(Workstream.user_id == user_id)
            )
            ws_count = result.scalar() or 0
            if ws_count > 0:
                facts.append(
                    f"You have {ws_count} active workstream{'s' if ws_count != 1 else ''}"
                )
        except Exception:
            pass

        # Count total cards
        try:
            result = await db.execute(select(func.count(Card.id)))
            card_count = result.scalar() or 0
            if card_count > 0:
                facts.append(
                    f"GrantScope is monitoring {card_count} signals across all pillars"
                )
        except Exception:
            pass

        # Count conversations
        try:
            result = await db.execute(
                select(func.count(ChatConversation.id)).where(
                    ChatConversation.user_id == user_id
                )
            )
            conv_count = result.scalar() or 0
            if conv_count > 0:
                facts.append(
                    f"You've had {conv_count} conversation{'s' if conv_count != 1 else ''} with GrantScope"
                )
        except Exception:
            pass

        # Count pinned messages
        try:
            result = await db.execute(
                select(func.count(ChatPinnedMessage.id)).where(
                    ChatPinnedMessage.user_id == user_id
                )
            )
            pin_count = result.scalar() or 0
            if pin_count > 0:
                facts.append(
                    f"You've saved {pin_count} insight{'s' if pin_count != 1 else ''}"
                )
        except Exception:
            pass

        return {"facts": facts}
    except Exception as e:
        logger.error(f"Failed to get chat stats: {e}")
        return {"facts": []}


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Main chat endpoint for Ask GrantScope NLQ feature.

    Streams an AI-powered response using Server-Sent Events (SSE).
    Supports four scopes:
    - signal: Q&A about a specific card and its sources
    - workstream: Analysis across cards in a workstream
    - global: Broad strategic intelligence search
    - wizard: Grant application advisor interview

    Returns streaming SSE events:
    - {"type": "token", "content": "..."} -- incremental response tokens
    - {"type": "citation", "data": {...}} -- resolved source citations
    - {"type": "suggestions", "data": [...]} -- follow-up question suggestions
    - {"type": "done", "data": {"conversation_id": "...", "message_id": "..."}}
    - {"type": "error", "content": "..."} -- error messages
    """
    user_id = current_user["id"]

    # Validate scope
    valid_scopes = ("signal", "workstream", "global", "wizard", "grant_assistant")
    if request.scope not in valid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope. Must be one of: {', '.join(valid_scopes)}.",
        )

    # Validate scope_id is provided for scopes that require it
    # (global and grant_assistant do NOT require scope_id)
    if request.scope in ("signal", "workstream", "wizard") and not request.scope_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"scope_id is required for '{request.scope}' scope.",
        )

    # Convert MentionRef models to dicts for the service layer
    mention_dicts = None
    if request.mentions:
        mention_dicts = [m.model_dump() for m in request.mentions]

    # Query admin settings for grant_assistant scope
    online_search_enabled = False
    max_online_searches: int | None = None
    if request.scope == "grant_assistant":
        try:
            from app.models.db.system_settings import SystemSetting

            settings_result = await db.execute(
                select(SystemSetting.key, SystemSetting.value).where(
                    SystemSetting.key.in_(
                        ["online_search_enabled", "max_online_searches_per_turn"]
                    )
                )
            )
            settings_map = {row[0]: row[1] for row in settings_result.all()}

            raw_online = settings_map.get("online_search_enabled")
            if raw_online is not None:
                online_search_enabled = (
                    raw_online is True or str(raw_online).lower() == "true"
                )

            raw_max = settings_map.get("max_online_searches_per_turn")
            if raw_max is not None:
                try:
                    max_online_searches = int(raw_max)
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.warning(f"Failed to query grant assistant settings: {e}")

    async def event_generator():
        async for event in chat_service_chat(
            request.scope,
            request.scope_id,
            request.message,
            request.conversation_id,
            user_id,
            db,
            mentions=mention_dicts,
            online_search_enabled=online_search_enabled,
            max_online_searches=max_online_searches,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# GET /chat/conversations
# ---------------------------------------------------------------------------


@router.get("/chat/conversations")
async def list_chat_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    scope_id: Optional[str] = Query(None, description="Filter by scope entity ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    List the current user's chat conversations.

    Returns conversations ordered by most recently updated.
    Supports pagination and optional scope/scope_id filtering.
    """
    user_id = current_user["id"]
    try:
        stmt = select(
            ChatConversation.id,
            ChatConversation.scope,
            ChatConversation.scope_id,
            ChatConversation.title,
            ChatConversation.created_at,
            ChatConversation.updated_at,
        ).where(ChatConversation.user_id == user_id)

        if scope:
            stmt = stmt.where(ChatConversation.scope == scope)
        if scope_id:
            stmt = stmt.where(ChatConversation.scope_id == scope_id)

        stmt = (
            stmt.order_by(ChatConversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(r.id),
                "scope": r.scope,
                "scope_id": str(r.scope_id) if r.scope_id else None,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Failed to list conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing conversations", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /chat/conversations/search
# ---------------------------------------------------------------------------


@router.get("/chat/conversations/search")
async def search_chat_conversations(
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Search conversations by title and message content.
    Uses ILIKE search across conversation titles and message content.
    """
    user_id = current_user["id"]
    try:
        search_term = f"%{q}%"

        # Search conversation titles
        title_stmt = (
            select(
                ChatConversation.id,
                ChatConversation.scope,
                ChatConversation.scope_id,
                ChatConversation.title,
                ChatConversation.created_at,
                ChatConversation.updated_at,
            )
            .where(
                ChatConversation.user_id == user_id,
                ChatConversation.title.ilike(search_term),
            )
            .order_by(ChatConversation.updated_at.desc())
            .limit(limit)
        )
        title_result = await db.execute(title_stmt)
        title_rows = title_result.all()

        # Search message content
        msg_stmt = (
            select(ChatMessage.conversation_id)
            .where(ChatMessage.content.ilike(search_term))
            .distinct()
            .limit(50)
        )
        msg_result = await db.execute(msg_stmt)
        msg_conv_ids = [r.conversation_id for r in msg_result.all()]

        # Fetch those conversations (with ownership check)
        msg_conversations = []
        if msg_conv_ids:
            conv_stmt = (
                select(
                    ChatConversation.id,
                    ChatConversation.scope,
                    ChatConversation.scope_id,
                    ChatConversation.title,
                    ChatConversation.created_at,
                    ChatConversation.updated_at,
                )
                .where(
                    ChatConversation.user_id == user_id,
                    ChatConversation.id.in_(msg_conv_ids),
                )
                .order_by(ChatConversation.updated_at.desc())
            )
            conv_result = await db.execute(conv_stmt)
            msg_conversations = conv_result.all()

        # Merge and deduplicate results, title matches first
        def _row_to_conv(r):
            return {
                "id": str(r.id),
                "scope": r.scope,
                "scope_id": str(r.scope_id) if r.scope_id else None,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }

        seen: set = set()
        results: list = []
        for r in list(title_rows) + list(msg_conversations):
            rid = str(r.id)
            if rid not in seen:
                seen.add(rid)
                results.append(_row_to_conv(r))
                if len(results) >= limit:
                    break

        return results
    except Exception as e:
        logger.error(f"Failed to search conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error("searching conversations", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@router.get("/chat/conversations/{conversation_id}")
async def get_chat_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get a specific conversation with all its messages.

    Returns the conversation metadata and messages ordered chronologically.
    """
    user_id = current_user["id"]
    try:
        # Fetch conversation and verify ownership
        conv_result = await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        conv = conv_result.scalars().first()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        conversation = _row_to_dict(conv)

        # Fetch messages
        msg_result = await db.execute(
            select(
                ChatMessage.id,
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.citations,
                ChatMessage.tokens_used,
                ChatMessage.model,
                ChatMessage.created_at,
            )
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at)
        )
        messages = [
            {
                "id": str(r.id),
                "role": r.role,
                "content": r.content,
                "citations": r.citations,
                "tokens_used": r.tokens_used,
                "model": r.model,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in msg_result.all()
        ]

        return {"conversation": conversation, "messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get conversation {conversation_id} for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("fetching conversation", e),
        ) from e


# ---------------------------------------------------------------------------
# PATCH /chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@router.patch("/chat/conversations/{conversation_id}")
async def update_chat_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Update a conversation's title.

    Only the conversation owner can rename it.
    """
    user_id = current_user["id"]
    try:
        # Fetch conversation to verify it exists
        conv_result = await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
            )
        )
        conv = conv_result.scalars().first()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Verify ownership
        if str(conv.user_id) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this conversation",
            )

        # Update the title
        conv.title = body.title
        await db.commit()
        await db.refresh(conv)

        return _row_to_dict(conv)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Failed to update conversation {conversation_id} for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating conversation", e),
        ) from e


# ---------------------------------------------------------------------------
# DELETE /chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------


@router.delete("/chat/conversations/{conversation_id}")
async def delete_chat_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Delete a conversation and all its messages.

    Messages are cascade-deleted via the foreign key constraint.
    """
    user_id = current_user["id"]
    try:
        # Verify ownership first
        conv_result = await db.execute(
            select(ChatConversation.id).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        conv = conv_result.first()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Delete conversation (messages cascade-deleted via FK)
        await db.execute(
            delete(ChatConversation).where(
                ChatConversation.id == conversation_id,
            )
        )
        await db.commit()

        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Failed to delete conversation {conversation_id} for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("deleting conversation", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /chat/suggestions
# ---------------------------------------------------------------------------


@router.get("/chat/suggestions")
async def chat_suggestions(
    scope: str = Query(
        ...,
        description="Chat scope: signal, workstream, global, wizard, or grant_assistant",
    ),
    scope_id: Optional[str] = Query(None, description="ID of the scoped entity"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get AI-generated suggested questions for a given scope.

    Returns context-aware starter questions to help users begin
    exploring a signal, workstream, global strategic intelligence,
    wizard interview, or grant assistant conversation.
    """
    user_id = current_user["id"]

    valid_scopes = ("signal", "workstream", "global", "wizard", "grant_assistant")
    if scope not in valid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope. Must be one of: {', '.join(valid_scopes)}.",
        )

    try:
        return await chat_generate_suggestions(
            scope,
            scope_id,
            db,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Failed to generate chat suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("generating suggestions", e),
        ) from e


# ---------------------------------------------------------------------------
# GET /chat/suggestions/smart
# ---------------------------------------------------------------------------


@router.get("/chat/suggestions/smart")
async def smart_chat_suggestions(
    scope: str = Query(
        ...,
        description="Chat scope: signal, workstream, global, wizard, or grant_assistant",
    ),
    scope_id: Optional[str] = Query(None, description="ID of the scoped entity"),
    conversation_id: Optional[str] = Query(
        None, description="Conversation ID for context-aware suggestions"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Get AI-generated smart follow-up suggestions with categories.

    When a conversation_id is provided, fetches the last 3 messages from
    that conversation and uses the context to generate more relevant
    categorized suggestions.

    Categories: deeper, compare, action, explore
    """
    user_id = current_user["id"]

    valid_scopes = ("signal", "workstream", "global", "wizard", "grant_assistant")
    if scope not in valid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scope. Must be one of: {', '.join(valid_scopes)}.",
        )

    try:
        conversation_summary = ""

        # If conversation_id provided, fetch recent messages for context
        if conversation_id:
            try:
                # Verify conversation ownership
                conv_result = await db.execute(
                    select(
                        ChatConversation.id,
                        ChatConversation.scope,
                        ChatConversation.scope_id,
                        ChatConversation.title,
                    ).where(
                        ChatConversation.id == conversation_id,
                        ChatConversation.user_id == user_id,
                    )
                )
                conv = conv_result.first()
                if conv:
                    # Fetch last 3 messages from the conversation
                    msg_result = await db.execute(
                        select(ChatMessage.role, ChatMessage.content)
                        .where(ChatMessage.conversation_id == conversation_id)
                        .order_by(ChatMessage.created_at.desc())
                        .limit(3)
                    )
                    msg_rows = msg_result.all()
                    if msg_rows:
                        # Build a brief summary of recent exchange
                        recent_msgs = list(reversed(msg_rows))
                        parts = []
                        for msg in recent_msgs:
                            role_label = "User" if msg.role == "user" else "Assistant"
                            # Truncate long messages
                            content = (msg.content or "")[:300]
                            parts.append(f"{role_label}: {content}")
                        conversation_summary = "\n".join(parts)
            except Exception as e:
                logger.warning(
                    f"Failed to fetch conversation context for smart suggestions: {e}"
                )

        # Build scope context
        scope_context = ""
        try:
            if scope == "signal" and scope_id:
                card_result = await db.execute(
                    select(Card.name, Card.summary).where(Card.id == scope_id)
                )
                card = card_result.first()
                if card:
                    scope_context = f"Signal: \"{card.name or 'Unknown'}\". Summary: {(card.summary or '')[:200]}"
            elif scope == "workstream" and scope_id:
                ws_result = await db.execute(
                    select(Workstream.name, Workstream.description).where(
                        Workstream.id == scope_id
                    )
                )
                ws = ws_result.first()
                if ws:
                    scope_context = f"Workstream: \"{ws.name or 'Unknown'}\". Description: {(ws.description or '')[:200]}"
            else:
                scope_context = "Global strategic intelligence for the City of Austin."
        except Exception as e:
            logger.warning(f"Failed to fetch scope context for smart suggestions: {e}")

        # Generate categorized suggestions via LLM
        suggestions = await generate_smart_suggestions(
            scope=scope,
            scope_context=scope_context,
            conversation_summary=conversation_summary,
        )

        return {"suggestions": suggestions}

    except Exception as e:
        logger.error(f"Failed to generate smart chat suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("generating smart suggestions", e),
        ) from e


# ---------------------------------------------------------------------------
# @mention search (cross-scope references)
# ---------------------------------------------------------------------------


@router.get("/chat/mentions/search")
async def search_mentions(
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    limit: int = Query(8, ge=1, le=20, description="Max results"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Search signals (cards) and workstreams for @mention autocomplete.

    Returns a combined list of matching entities, cards first, then workstreams,
    limited to the requested number of results.
    """
    try:
        results: List[Dict[str, Any]] = []
        search_term = f"%{q}%"

        # Search cards (signals) by name
        try:
            cards_result = await db.execute(
                select(Card.id, Card.name, Card.slug)
                .where(Card.name.ilike(search_term))
                .order_by(Card.name)
                .limit(limit)
            )
            for card in cards_result.all():
                results.append(
                    {
                        "id": str(card.id),
                        "type": "signal",
                        "title": card.name,
                        "slug": card.slug,
                    }
                )
        except Exception as exc:
            logger.warning(f"Mention search: cards query failed: {exc}")

        # Search workstreams by name
        remaining = limit - len(results)
        if remaining > 0:
            try:
                ws_result = await db.execute(
                    select(Workstream.id, Workstream.name)
                    .where(Workstream.name.ilike(search_term))
                    .order_by(Workstream.name)
                    .limit(remaining)
                )
                for ws in ws_result.all():
                    results.append(
                        {
                            "id": str(ws.id),
                            "type": "workstream",
                            "title": ws.name,
                        }
                    )
            except Exception as exc:
                logger.warning(f"Mention search: workstreams query failed: {exc}")

        return {"results": results[:limit]}
    except Exception as e:
        logger.error(f"Failed to search mentions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("searching mentions", e),
        ) from e


# ---------------------------------------------------------------------------
# Pin / save messages
# ---------------------------------------------------------------------------


@router.post("/chat/messages/{message_id}/pin")
async def pin_chat_message(
    message_id: str,
    body: dict = None,  # optional { "note": "..." }
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Pin a chat message for quick reference."""
    user_id = current_user["id"]
    try:
        # Verify the message exists and belongs to user's conversation
        msg_result = await db.execute(
            select(ChatMessage.id, ChatMessage.conversation_id).where(
                ChatMessage.id == message_id
            )
        )
        msg = msg_result.first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        conversation_id = str(msg.conversation_id)

        # Verify user owns the conversation
        conv_result = await db.execute(
            select(ChatConversation.id).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        if not conv_result.first():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized",
            )

        # Check if pin already exists (upsert behaviour)
        existing_result = await db.execute(
            select(ChatPinnedMessage).where(
                ChatPinnedMessage.user_id == user_id,
                ChatPinnedMessage.message_id == message_id,
            )
        )
        existing_pin = existing_result.scalars().first()

        note = (body or {}).get("note")

        if existing_pin:
            # Update the note on existing pin
            existing_pin.note = note
            await db.commit()
            await db.refresh(existing_pin)
            return _row_to_dict(existing_pin)
        else:
            # Create new pin
            new_pin = ChatPinnedMessage(
                user_id=user_id,
                message_id=message_id,
                conversation_id=conversation_id,
                note=note,
            )
            db.add(new_pin)
            await db.commit()
            await db.refresh(new_pin)
            return _row_to_dict(new_pin)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to pin message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pinning message", e),
        ) from e


@router.delete("/chat/messages/{message_id}/pin")
async def unpin_chat_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """Unpin a chat message."""
    user_id = current_user["id"]
    try:
        await db.execute(
            delete(ChatPinnedMessage).where(
                ChatPinnedMessage.user_id == user_id,
                ChatPinnedMessage.message_id == message_id,
            )
        )
        await db.commit()
        return {"status": "unpinned", "message_id": message_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to unpin message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("unpinning message", e),
        ) from e


@router.get("/chat/pins")
async def list_pinned_messages(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """List user's pinned messages with conversation context."""
    user_id = current_user["id"]
    try:
        # Fetch pinned messages with joined message and conversation data
        stmt = (
            select(ChatPinnedMessage)
            .where(ChatPinnedMessage.user_id == user_id)
            .order_by(ChatPinnedMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        pins = list(result.scalars().all())

        # Build enriched response by joining with messages and conversations
        enriched = []
        for pin in pins:
            pin_dict = _row_to_dict(pin)

            # Fetch the associated message
            msg_result = await db.execute(
                select(
                    ChatMessage.id,
                    ChatMessage.content,
                    ChatMessage.role,
                    ChatMessage.citations,
                    ChatMessage.created_at,
                ).where(ChatMessage.id == pin.message_id)
            )
            msg = msg_result.first()
            if msg:
                pin_dict["chat_messages"] = {
                    "id": str(msg.id),
                    "content": msg.content,
                    "role": msg.role,
                    "citations": msg.citations,
                    "created_at": (
                        msg.created_at.isoformat() if msg.created_at else None
                    ),
                }
            else:
                pin_dict["chat_messages"] = None

            # Fetch the associated conversation
            conv_result = await db.execute(
                select(
                    ChatConversation.id,
                    ChatConversation.title,
                    ChatConversation.scope,
                ).where(ChatConversation.id == pin.conversation_id)
            )
            conv = conv_result.first()
            if conv:
                pin_dict["chat_conversations"] = {
                    "id": str(conv.id),
                    "title": conv.title,
                    "scope": conv.scope,
                }
            else:
                pin_dict["chat_conversations"] = None

            enriched.append(pin_dict)

        return enriched
    except Exception as e:
        logger.error(f"Failed to list pins for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing pins", e),
        ) from e


# ---------------------------------------------------------------------------
# PDF export for chat messages
# ---------------------------------------------------------------------------


def _cleanup_temp_file(path: str):
    """Remove a temporary file after it has been sent in a response."""
    try:
        if path and Path(path).exists():
            os.unlink(path)
    except Exception as exc:
        logger.warning(f"Failed to clean up temp file {path}: {exc}")


@router.get("/chat/messages/{message_id}/export/pdf")
async def export_chat_message_pdf(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_hardcoded),
):
    """
    Export a chat assistant message as a professional PDF document.

    Generates a mayor-ready PDF matching the executive brief style,
    including the user's question, the AI analysis, and any citations.

    The exported message must be an assistant response belonging to a
    conversation owned by the authenticated user.
    """
    user_id = current_user["id"]

    try:
        # 1. Fetch the target message
        msg_result = await db.execute(
            select(
                ChatMessage.id,
                ChatMessage.conversation_id,
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.citations,
                ChatMessage.model,
                ChatMessage.created_at,
            ).where(ChatMessage.id == message_id)
        )
        message = msg_result.first()
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        conversation_id = str(message.conversation_id)
        message_created_at = (
            message.created_at.isoformat() if message.created_at else None
        )

        # 2. Verify conversation ownership
        conv_result = await db.execute(
            select(
                ChatConversation.id,
                ChatConversation.title,
                ChatConversation.scope,
                ChatConversation.scope_id,
                ChatConversation.user_id,
            ).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        conversation = conv_result.first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to export this message",
            )

        # 3. Fetch the preceding user message (the question)
        question_text = ""
        try:
            if message_created_at:
                prev_msgs = await db.execute(
                    select(
                        ChatMessage.role, ChatMessage.content, ChatMessage.created_at
                    )
                    .where(
                        ChatMessage.conversation_id == conversation_id,
                        ChatMessage.role == "user",
                        ChatMessage.created_at < message.created_at,
                    )
                    .order_by(ChatMessage.created_at.desc())
                    .limit(1)
                )
                prev = prev_msgs.first()
                if prev:
                    question_text = prev.content or ""
        except Exception as exc:
            logger.warning(f"Could not fetch preceding question for export: {exc}")

        # 4. Resolve scope context name
        scope_val = conversation.scope
        scope_id_val = str(conversation.scope_id) if conversation.scope_id else None
        scope_context = None

        if scope_val == "signal" and scope_id_val:
            try:
                card_res = await db.execute(
                    select(Card.name).where(Card.id == scope_id_val)
                )
                card_row = card_res.first()
                if card_row:
                    scope_context = card_row.name
            except Exception:
                pass
        elif scope_val == "workstream" and scope_id_val:
            try:
                ws_res = await db.execute(
                    select(Workstream.name).where(Workstream.id == scope_id_val)
                )
                ws_row = ws_res.first()
                if ws_row:
                    scope_context = ws_row.name
            except Exception:
                pass

        # 5. Parse citations
        citations = message.citations or []
        if isinstance(citations, str):
            try:
                citations = json.loads(citations)
            except (json.JSONDecodeError, TypeError):
                citations = []

        # 6. Build metadata
        metadata: Dict[str, Any] = {}
        if citations:
            metadata["source_count"] = len(citations)
        if message.model:
            metadata["model"] = message.model

        # 7. Generate the PDF
        title = conversation.title or "GrantScope2 Intelligence Response"
        export_service = ExportService(db)
        pdf_path = await export_service.generate_chat_response_pdf(
            title=title,
            question=question_text,
            response_content=message.content or "",
            citations=citations if citations else None,
            metadata=metadata if metadata else None,
            scope=scope_val,
            scope_context=scope_context,
        )

        # 8. Return file with cleanup
        short_id = message_id[:8] if len(message_id) >= 8 else message_id
        filename = f"grantscope-response-{short_id}.pdf"

        return FileResponse(
            path=pdf_path,
            filename=filename,
            media_type="application/pdf",
            background=BackgroundTask(_cleanup_temp_file, pdf_path),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export chat message {message_id} as PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("exporting chat message as PDF", e),
        ) from e
