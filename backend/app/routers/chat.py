"""Chat (Ask Foresight) router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.deps import supabase, get_current_user, _safe_error
from app.models.chat import ChatRequest, ConversationUpdateRequest
from app.chat_service import (
    chat as chat_service_chat,
    generate_suggestions as chat_generate_suggestions,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


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

    async def event_generator():
        async for event in chat_service_chat(
            scope=request.scope,
            scope_id=request.scope_id,
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=user_id,
            supabase_client=supabase,
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
