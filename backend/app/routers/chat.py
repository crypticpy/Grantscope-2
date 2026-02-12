"""Chat (Ask Foresight) router."""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, FileResponse
from starlette.background import BackgroundTask

from app.deps import supabase, get_current_user, _safe_error
from app.models.chat import ChatRequest, ConversationUpdateRequest
from app.export_service import ExportService
from app.chat_service import (
    chat as chat_service_chat,
    generate_suggestions as chat_generate_suggestions,
)
from app.openai_provider import azure_openai_async_client, get_chat_mini_deployment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.get("/chat/stats")
async def chat_stats(
    current_user: dict = Depends(get_current_user),
):
    """
    Get lightweight stats for the chat empty state.
    Returns facts about the user's intelligence data.
    """
    user_id = current_user["id"]
    try:
        facts = []

        # Count followed signals
        try:
            follows = (
                supabase.table("user_follows")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            if follows.count and follows.count > 0:
                facts.append(
                    f"You're tracking {follows.count} signal{'s' if follows.count != 1 else ''}"
                )
        except Exception:
            pass

        # Count workstreams
        try:
            ws = (
                supabase.table("workstreams")
                .select("id", count="exact")
                .eq("created_by", user_id)
                .execute()
            )
            if ws.count and ws.count > 0:
                facts.append(
                    f"You have {ws.count} active workstream{'s' if ws.count != 1 else ''}"
                )
        except Exception:
            pass

        # Count total cards
        try:
            cards = supabase.table("cards").select("id", count="exact").execute()
            if cards.count and cards.count > 0:
                facts.append(
                    f"Foresight is monitoring {cards.count} signals across all pillars"
                )
        except Exception:
            pass

        # Count conversations
        try:
            convs = (
                supabase.table("chat_conversations")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            if convs.count and convs.count > 0:
                facts.append(
                    f"You've had {convs.count} conversation{'s' if convs.count != 1 else ''} with Foresight"
                )
        except Exception:
            pass

        # Count pinned messages
        try:
            pins = (
                supabase.table("chat_pinned_messages")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            if pins.count and pins.count > 0:
                facts.append(
                    f"You've saved {pins.count} insight{'s' if pins.count != 1 else ''}"
                )
        except Exception:
            pass

        return {"facts": facts}
    except Exception as e:
        logger.error(f"Failed to get chat stats: {e}")
        return {"facts": []}


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint for Ask Foresight NLQ feature.

    Streams an AI-powered response using Server-Sent Events (SSE).
    Supports three scopes:
    - signal: Q&A about a specific card and its sources
    - workstream: Analysis across cards in a workstream
    - global: Broad strategic intelligence search

    Returns streaming SSE events:
    - {"type": "token", "content": "..."} -- incremental response tokens
    - {"type": "citation", "data": {...}} -- resolved source citations
    - {"type": "suggestions", "data": [...]} -- follow-up question suggestions
    - {"type": "done", "data": {"conversation_id": "...", "message_id": "..."}}
    - {"type": "error", "content": "..."} -- error messages
    """
    user_id = current_user["id"]

    # Validate scope
    if request.scope not in ("signal", "workstream", "global"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scope. Must be 'signal', 'workstream', or 'global'.",
        )

    # Validate scope_id is provided for non-global scopes
    if request.scope in ("signal", "workstream") and not request.scope_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"scope_id is required for '{request.scope}' scope.",
        )

    # Convert MentionRef models to dicts for the service layer
    mention_dicts = None
    if request.mentions:
        mention_dicts = [m.model_dump() for m in request.mentions]

    async def event_generator():
        async for event in chat_service_chat(
            scope=request.scope,
            scope_id=request.scope_id,
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=user_id,
            supabase_client=supabase,
            mentions=mention_dicts,
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


@router.get("/chat/conversations")
async def list_chat_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    scope: Optional[str] = Query(None, description="Filter by scope"),
    scope_id: Optional[str] = Query(None, description="Filter by scope entity ID"),
    current_user: dict = Depends(get_current_user),
):
    """
    List the current user's chat conversations.

    Returns conversations ordered by most recently updated.
    Supports pagination and optional scope/scope_id filtering.
    """
    user_id = current_user["id"]
    try:
        query = (
            supabase.table("chat_conversations")
            .select("id, scope, scope_id, title, created_at, updated_at")
            .eq("user_id", user_id)
        )

        if scope:
            query = query.eq("scope", scope)
        if scope_id:
            query = query.eq("scope_id", scope_id)

        query = query.order("updated_at", desc=True).range(offset, offset + limit - 1)

        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to list conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing conversations", e),
        ) from e


@router.get("/chat/conversations/search")
async def search_chat_conversations(
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """
    Search conversations by title and message content.
    Uses Postgres full-text search across conversation titles and message content.
    """
    user_id = current_user["id"]
    try:
        # Search conversation titles
        title_result = (
            supabase.table("chat_conversations")
            .select("id, scope, scope_id, title, created_at, updated_at")
            .eq("user_id", user_id)
            .ilike("title", f"%{q}%")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )

        # Search message content
        msg_result = (
            supabase.table("chat_messages")
            .select("conversation_id, content")
            .ilike("content", f"%{q}%")
            .limit(50)
            .execute()
        )

        # Get unique conversation IDs from message matches
        msg_conv_ids = list(set(m["conversation_id"] for m in (msg_result.data or [])))

        # Fetch those conversations (with ownership check)
        msg_conversations = []
        if msg_conv_ids:
            conv_result = (
                supabase.table("chat_conversations")
                .select("id, scope, scope_id, title, created_at, updated_at")
                .eq("user_id", user_id)
                .in_("id", msg_conv_ids)
                .order("updated_at", desc=True)
                .execute()
            )
            msg_conversations = conv_result.data or []

        # Merge and deduplicate results, title matches first
        seen = set()
        results = []
        for conv in (title_result.data or []) + msg_conversations:
            if conv["id"] not in seen:
                seen.add(conv["id"])
                results.append(conv)
                if len(results) >= limit:
                    break

        return results
    except Exception as e:
        logger.error(f"Failed to search conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error("searching conversations", e),
        ) from e


@router.get("/chat/conversations/{conversation_id}")
async def get_chat_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get a specific conversation with all its messages.

    Returns the conversation metadata and messages ordered chronologically.
    """
    user_id = current_user["id"]
    try:
        # Fetch conversation and verify ownership
        conv_result = (
            supabase.table("chat_conversations")
            .select("*")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        conversation = conv_result.data[0]

        # Fetch messages
        msg_result = (
            supabase.table("chat_messages")
            .select("id, role, content, citations, tokens_used, model, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )

        messages = msg_result.data or []
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


@router.patch("/chat/conversations/{conversation_id}")
async def update_chat_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update a conversation's title.

    Only the conversation owner can rename it.
    """
    user_id = current_user["id"]
    try:
        # Fetch conversation to verify it exists
        conv_result = (
            supabase.table("chat_conversations")
            .select("id, user_id")
            .eq("id", conversation_id)
            .execute()
        )

        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Verify ownership
        if conv_result.data[0]["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this conversation",
            )

        # Update the title
        update_result = (
            supabase.table("chat_conversations")
            .update({"title": body.title})
            .eq("id", conversation_id)
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update conversation",
            )

        return update_result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update conversation {conversation_id} for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("updating conversation", e),
        ) from e


@router.delete("/chat/conversations/{conversation_id}")
async def delete_chat_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a conversation and all its messages.

    Messages are cascade-deleted via the foreign key constraint.
    """
    user_id = current_user["id"]
    try:
        # Verify ownership first
        conv_result = (
            supabase.table("chat_conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Delete conversation (messages cascade-deleted via FK)
        supabase.table("chat_conversations").delete().eq(
            "id", conversation_id
        ).execute()

        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete conversation {conversation_id} for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("deleting conversation", e),
        ) from e


@router.get("/chat/suggestions")
async def chat_suggestions(
    scope: str = Query(..., description="Chat scope: signal, workstream, or global"),
    scope_id: Optional[str] = Query(None, description="ID of the scoped entity"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get AI-generated suggested questions for a given scope.

    Returns context-aware starter questions to help users begin
    exploring a signal, workstream, or global strategic intelligence.
    """
    user_id = current_user["id"]

    if scope not in ("signal", "workstream", "global"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scope. Must be 'signal', 'workstream', or 'global'.",
        )

    try:
        return await chat_generate_suggestions(
            scope=scope,
            scope_id=scope_id,
            supabase_client=supabase,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Failed to generate chat suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("generating suggestions", e),
        ) from e


@router.get("/chat/suggestions/smart")
async def smart_chat_suggestions(
    scope: str = Query(..., description="Chat scope: signal, workstream, or global"),
    scope_id: Optional[str] = Query(None, description="ID of the scoped entity"),
    conversation_id: Optional[str] = Query(
        None, description="Conversation ID for context-aware suggestions"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get AI-generated smart follow-up suggestions with categories.

    When a conversation_id is provided, fetches the last 3 messages from
    that conversation and uses the context to generate more relevant
    categorized suggestions.

    Categories: deeper, compare, action, explore
    """
    user_id = current_user["id"]

    if scope not in ("signal", "workstream", "global"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scope. Must be 'signal', 'workstream', or 'global'.",
        )

    try:
        conversation_summary = ""

        # If conversation_id provided, fetch recent messages for context
        if conversation_id:
            try:
                # Verify conversation ownership
                conv_result = (
                    supabase.table("chat_conversations")
                    .select("id, scope, scope_id, title")
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .execute()
                )
                if conv_result.data:
                    # Fetch last 3 messages from the conversation
                    msg_result = (
                        supabase.table("chat_messages")
                        .select("role, content")
                        .eq("conversation_id", conversation_id)
                        .order("created_at", desc=True)
                        .limit(3)
                        .execute()
                    )
                    if msg_result.data:
                        # Build a brief summary of recent exchange
                        recent_msgs = list(reversed(msg_result.data))
                        parts = []
                        for msg in recent_msgs:
                            role_label = (
                                "User" if msg["role"] == "user" else "Assistant"
                            )
                            # Truncate long messages
                            content = (msg.get("content") or "")[:300]
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
                card_result = (
                    supabase.table("cards")
                    .select("name, summary")
                    .eq("id", scope_id)
                    .execute()
                )
                if card_result.data:
                    card = card_result.data[0]
                    scope_context = f"Signal: \"{card.get('name', 'Unknown')}\". Summary: {(card.get('summary') or '')[:200]}"
            elif scope == "workstream" and scope_id:
                ws_result = (
                    supabase.table("workstreams")
                    .select("name, description")
                    .eq("id", scope_id)
                    .execute()
                )
                if ws_result.data:
                    ws = ws_result.data[0]
                    scope_context = f"Workstream: \"{ws.get('name', 'Unknown')}\". Description: {(ws.get('description') or '')[:200]}"
            else:
                scope_context = "Global strategic intelligence for the City of Austin."
        except Exception as e:
            logger.warning(f"Failed to fetch scope context for smart suggestions: {e}")

        # Generate categorized suggestions via LLM
        suggestions = await _generate_smart_suggestions(
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


async def _generate_smart_suggestions(
    scope: str,
    scope_context: str,
    conversation_summary: str,
) -> List[Dict[str, str]]:
    """
    Generate categorized follow-up suggestions using the mini model.

    Returns a list of dicts with 'text' and 'category' keys.
    Categories: deeper, compare, action, explore
    """
    context_block = ""
    if conversation_summary:
        context_block = f"""
Recent conversation:
{conversation_summary}
"""

    prompt = f"""Generate exactly 4 follow-up question suggestions for a city analyst using a strategic intelligence system.

Scope: {scope}
{scope_context}
{context_block}
Each suggestion must belong to one of these categories:
- "deeper": Dig deeper into causes, drivers, or details
- "compare": Compare with other cities, trends, or benchmarks
- "action": Identify specific actions, next steps, or recommendations
- "explore": Discover related signals, patterns, or connections

Return a JSON object with a "suggestions" array of exactly 4 objects, one per category.
Each object has "text" (the question, max 80 chars) and "category" (one of: deeper, compare, action, explore).

Example:
{{"suggestions": [
  {{"text": "What are the underlying drivers of this trend?", "category": "deeper"}},
  {{"text": "How does this compare to Denver and Portland?", "category": "compare"}},
  {{"text": "What specific actions should Austin take next?", "category": "action"}},
  {{"text": "What related signals should we watch?", "category": "explore"}}
]}}"""

    try:
        response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate categorized follow-up questions for a strategic "
                        "intelligence chat system. Respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.8,
        )

        content = response.choices[0].message.content.strip()
        result = json.loads(content)

        # Parse the result
        suggestions_raw: list = []
        if isinstance(result, dict):
            suggestions_raw = result.get("suggestions") or result.get("questions") or []
        elif isinstance(result, list):
            suggestions_raw = result

        valid_categories = {"deeper", "compare", "action", "explore"}
        suggestions: List[Dict[str, str]] = []
        for item in suggestions_raw[:4]:
            if isinstance(item, dict) and "text" in item and "category" in item:
                category = (
                    item["category"]
                    if item["category"] in valid_categories
                    else "deeper"
                )
                suggestions.append(
                    {
                        "text": str(item["text"])[:100],
                        "category": category,
                    }
                )

        if suggestions:
            return suggestions

    except Exception as e:
        logger.warning(f"Smart suggestion generation failed: {e}")

    # Fallback categorized suggestions
    fallbacks = {
        "signal": [
            {
                "text": "What are the underlying drivers of this signal?",
                "category": "deeper",
            },
            {"text": "How does this compare to other cities?", "category": "compare"},
            {"text": "What should Austin do to prepare?", "category": "action"},
            {"text": "What related signals should we track?", "category": "explore"},
        ],
        "workstream": [
            {"text": "What are the cross-cutting themes here?", "category": "deeper"},
            {
                "text": "How do these signals compare to national trends?",
                "category": "compare",
            },
            {
                "text": "Which signals require the most urgent action?",
                "category": "action",
            },
            {
                "text": "What emerging patterns connect these signals?",
                "category": "explore",
            },
        ],
        "global": [
            {
                "text": "What are the fastest-moving trends right now?",
                "category": "deeper",
            },
            {"text": "How does Austin compare to peer cities?", "category": "compare"},
            {
                "text": "What should Austin prioritize in the next 12 months?",
                "category": "action",
            },
            {
                "text": "Are there any new cross-cutting patterns emerging?",
                "category": "explore",
            },
        ],
    }
    return fallbacks.get(scope, fallbacks["global"])


# ---------------------------------------------------------------------------
# @mention search (cross-scope references)
# ---------------------------------------------------------------------------


@router.get("/chat/mentions/search")
async def search_mentions(
    q: str = Query(..., min_length=1, max_length=200, description="Search term"),
    limit: int = Query(8, ge=1, le=20, description="Max results"),
    current_user: dict = Depends(get_current_user),
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
            cards_result = (
                supabase.table("cards")
                .select("id, name, slug")
                .ilike("name", search_term)
                .order("name")
                .limit(limit)
                .execute()
            )
            for card in cards_result.data or []:
                results.append(
                    {
                        "id": card["id"],
                        "type": "signal",
                        "title": card["name"],
                        "slug": card.get("slug"),
                    }
                )
        except Exception as exc:
            logger.warning(f"Mention search: cards query failed: {exc}")

        # Search workstreams by name
        remaining = limit - len(results)
        if remaining > 0:
            try:
                ws_result = (
                    supabase.table("workstreams")
                    .select("id, name")
                    .ilike("name", search_term)
                    .order("name")
                    .limit(remaining)
                    .execute()
                )
                for ws in ws_result.data or []:
                    results.append(
                        {
                            "id": ws["id"],
                            "type": "workstream",
                            "title": ws["name"],
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
    current_user: dict = Depends(get_current_user),
):
    """Pin a chat message for quick reference."""
    user_id = current_user["id"]
    try:
        # Verify the message exists and belongs to user's conversation
        msg_result = (
            supabase.table("chat_messages")
            .select("id, conversation_id")
            .eq("id", message_id)
            .execute()
        )
        if not msg_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        conversation_id = msg_result.data[0]["conversation_id"]

        # Verify user owns the conversation
        conv_result = (
            supabase.table("chat_conversations")
            .select("id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized",
            )

        # Create pin (upsert so re-pinning just updates the note)
        pin_data = {
            "user_id": user_id,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "note": (body or {}).get("note"),
        }
        result = (
            supabase.table("chat_pinned_messages")
            .upsert(pin_data, on_conflict="user_id,message_id")
            .execute()
        )
        return result.data[0] if result.data else pin_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pin message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("pinning message", e),
        ) from e


@router.delete("/chat/messages/{message_id}/pin")
async def unpin_chat_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Unpin a chat message."""
    user_id = current_user["id"]
    try:
        supabase.table("chat_pinned_messages").delete().eq("user_id", user_id).eq(
            "message_id", message_id
        ).execute()
        return {"status": "unpinned", "message_id": message_id}
    except Exception as e:
        logger.error(f"Failed to unpin message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("unpinning message", e),
        ) from e


@router.get("/chat/pins")
async def list_pinned_messages(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """List user's pinned messages with conversation context."""
    user_id = current_user["id"]
    try:
        result = (
            supabase.table("chat_pinned_messages")
            .select(
                "*, chat_messages(id, content, role, citations, created_at), "
                "chat_conversations(id, title, scope)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []
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
    current_user: dict = Depends(get_current_user),
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
        msg_result = (
            supabase.table("chat_messages")
            .select("id, conversation_id, role, content, citations, model, created_at")
            .eq("id", message_id)
            .execute()
        )
        if not msg_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        message = msg_result.data[0]
        conversation_id = message["conversation_id"]

        # 2. Verify conversation ownership
        conv_result = (
            supabase.table("chat_conversations")
            .select("id, title, scope, scope_id, user_id")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to export this message",
            )

        conversation = conv_result.data[0]

        # 3. Fetch the preceding user message (the question)
        question_text = ""
        try:
            prev_msgs = (
                supabase.table("chat_messages")
                .select("role, content, created_at")
                .eq("conversation_id", conversation_id)
                .eq("role", "user")
                .lt("created_at", message["created_at"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if prev_msgs.data:
                question_text = prev_msgs.data[0].get("content", "")
        except Exception as exc:
            logger.warning(f"Could not fetch preceding question for export: {exc}")

        # 4. Resolve scope context name
        scope = conversation.get("scope")
        scope_id = conversation.get("scope_id")
        scope_context = None

        if scope == "signal" and scope_id:
            try:
                card_res = (
                    supabase.table("cards").select("name").eq("id", scope_id).execute()
                )
                if card_res.data:
                    scope_context = card_res.data[0].get("name")
            except Exception:
                pass
        elif scope == "workstream" and scope_id:
            try:
                ws_res = (
                    supabase.table("workstreams")
                    .select("name")
                    .eq("id", scope_id)
                    .execute()
                )
                if ws_res.data:
                    scope_context = ws_res.data[0].get("name")
            except Exception:
                pass

        # 5. Parse citations
        citations = message.get("citations") or []
        if isinstance(citations, str):
            try:
                citations = json.loads(citations)
            except (json.JSONDecodeError, TypeError):
                citations = []

        # 6. Build metadata
        metadata: Dict[str, Any] = {}
        if citations:
            metadata["source_count"] = len(citations)
        if message.get("model"):
            metadata["model"] = message["model"]

        # 7. Generate the PDF
        title = conversation.get("title") or "Foresight Intelligence Response"
        export_service = ExportService(supabase)
        pdf_path = await export_service.generate_chat_response_pdf(
            title=title,
            question=question_text,
            response_content=message.get("content", ""),
            citations=citations if citations else None,
            metadata=metadata if metadata else None,
            scope=scope,
            scope_context=scope_context,
        )

        # 8. Return file with cleanup
        short_id = message_id[:8] if len(message_id) >= 8 else message_id
        filename = f"foresight-response-{short_id}.pdf"

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
