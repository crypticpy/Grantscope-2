"""
Chat Models for AI Chat Endpoints

This module provides Pydantic models for the chat API endpoints,
supporting signal-scoped, workstream-scoped, and global chat interactions.

Supports:
- ChatRequest: Request model for the main chat endpoint
- ChatSuggestRequest: Request model for the suggestion endpoint
"""

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for the main chat endpoint."""

    scope: str = Field(
        ..., description="Chat scope: 'signal', 'workstream', or 'global'"
    )
    scope_id: Optional[str] = Field(
        None, description="card_id for signal scope, workstream_id for workstream scope"
    )
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    conversation_id: Optional[str] = Field(
        None, description="Existing conversation ID for multi-turn chat"
    )


class ChatSuggestRequest(BaseModel):
    """Request model for the suggestion endpoint."""

    scope: str = Field(
        ..., description="Chat scope: 'signal', 'workstream', or 'global'"
    )
    scope_id: Optional[str] = Field(
        None, description="card_id or workstream_id depending on scope"
    )


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation (e.g., renaming)."""

    title: str = Field(
        ..., min_length=1, max_length=200, description="New conversation title"
    )
