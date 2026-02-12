"""Chat (Ask Foresight) router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.deps import supabase, get_current_user, _safe_error
from app.models.chat import ChatRequest
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
    current_user: dict = Depends(get_current_user),
):
    """
    List the current user's chat conversations.

    Returns conversations ordered by most recently updated.
    Supports pagination and optional scope filtering.
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

        query = query.order("updated_at", desc=True).range(offset, offset + limit - 1)

        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to list conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("listing conversations", e),
        )


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
        )


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
        )


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
        suggestions = await chat_generate_suggestions(
            scope=scope,
            scope_id=scope_id,
            supabase_client=supabase,
            user_id=user_id,
        )
        return suggestions
    except Exception as e:
        logger.error(f"Failed to generate chat suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_safe_error("generating suggestions", e),
        )
