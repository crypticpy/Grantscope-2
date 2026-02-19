"""Conversation and message CRUD operations for the chat service.

Provides async database functions for creating, reading, and updating chat
conversations and their messages.  All functions accept an ``AsyncSession``
and are designed to be called from the chat orchestrator.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.chat import ChatConversation, ChatMessage
from app.openai_provider import azure_openai_async_client, get_chat_mini_deployment

logger = logging.getLogger(__name__)

# Maximum number of history messages to include in the LLM context
MAX_CONVERSATION_MESSAGES = 50


async def get_or_create_conversation(
    db: AsyncSession,
    user_id: str,
    scope: str,
    scope_id: Optional[str],
    conversation_id: Optional[str],
    first_message: str,
) -> Tuple[str, bool]:
    """Get an existing conversation or create a new one.

    When *conversation_id* is provided the function verifies ownership and
    returns it.  Otherwise a new conversation is created and a title is
    auto-generated via the mini LLM model.

    Args:
        db: Active async database session.
        user_id: UUID of the authenticated user.
        scope: Chat scope (``signal``, ``workstream``, ``global``, ``wizard``,
               or ``grant_assistant``).
        scope_id: UUID of the scoped entity (card, workstream, wizard session).
        conversation_id: Optional UUID of an existing conversation to resume.
        first_message: The user's opening message (used for title generation).

    Returns:
        A tuple of ``(conversation_id, is_new)`` where *is_new* is ``True``
        when a brand-new conversation was created.
    """
    if conversation_id:
        # Verify the conversation exists and belongs to the user
        result = await db.execute(
            select(ChatConversation.id).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            return str(row), False
        else:
            logger.warning(
                f"Conversation {conversation_id} not found for user {user_id}"
            )
            # Fall through to create new one

    # Generate title from first message using mini model
    title = first_message[:100]
    try:
        title_response = await azure_openai_async_client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[
                {
                    "role": "system",
                    "content": "Generate a concise title (max 60 chars) for a conversation "
                    "that starts with this message. Return ONLY the title text, "
                    "no quotes or extra formatting.",
                },
                {"role": "user", "content": first_message[:500]},
            ],
            max_tokens=30,
            temperature=0.5,
        )
        if generated_title := title_response.choices[0].message.content.strip():
            title = generated_title[:100]
    except Exception as e:
        logger.warning(f"Failed to generate conversation title: {e}")

    # Create new conversation
    now = datetime.now(timezone.utc)
    new_conv = ChatConversation(
        user_id=user_id,
        scope=scope,
        scope_id=scope_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    db.add(new_conv)
    await db.flush()
    await db.refresh(new_conv)

    return str(new_conv.id), True


async def get_conversation_history(
    db: AsyncSession,
    conversation_id: str,
) -> List[Dict[str, str]]:
    """Fetch recent conversation history for inclusion in the chat context.

    Args:
        db: Active async database session.
        conversation_id: UUID of the conversation.

    Returns:
        Messages in OpenAI format: ``[{"role": "...", "content": "..."}]``.
        Limited to :data:`MAX_CONVERSATION_MESSAGES`.
    """
    result = await db.execute(
        select(ChatMessage.role, ChatMessage.content)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(MAX_CONVERSATION_MESSAGES)
    )
    rows = result.all()

    # Reverse so the most recent N messages are in chronological order for the LLM
    return [{"role": msg.role, "content": msg.content} for msg in reversed(rows)]


async def store_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    citations: Optional[List[Dict]] = None,
    tokens_used: Optional[int] = None,
    model: Optional[str] = None,
    tool_calls: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Store a message in the database.

    Args:
        db: Active async database session.
        conversation_id: UUID of the parent conversation.
        role: Message role (``user``, ``assistant``, ``system``).
        content: The message text.
        citations: Optional list of citation dicts parsed from the response.
        tokens_used: Optional total token count for the response.
        model: Optional model deployment name used for this message.
        tool_calls: Optional dict of tool calls made during the response.
        metadata: Optional dict of additional metadata.

    Returns:
        The UUID string of the newly created message, or an empty string on
        failure.
    """
    now = datetime.now(timezone.utc)
    new_msg = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=citations or [],
        tokens_used=tokens_used,
        model=model,
        tool_calls=tool_calls,
        metadata_=metadata,
        created_at=now,
    )
    db.add(new_msg)
    await db.flush()
    await db.refresh(new_msg)

    if new_msg.id:
        return str(new_msg.id)

    logger.error(f"Failed to store {role} message for conversation {conversation_id}")
    return ""


async def update_conversation_timestamp(db: AsyncSession, conversation_id: str) -> None:
    """Update the conversation's ``updated_at`` timestamp.

    Args:
        db: Active async database session.
        conversation_id: UUID of the conversation to touch.
    """
    try:
        await db.execute(
            sa_update(ChatConversation)
            .where(ChatConversation.id == conversation_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await db.flush()
    except Exception as e:
        logger.warning(f"Failed to update conversation timestamp: {e}")
