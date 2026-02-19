"""Chat service package.

Modular components for the GrantScope chat system:

- sse: Server-Sent Events formatting utilities
- admin_deps: Admin authentication dependencies
- prompts: System prompt builders for each chat scope
- conversations: Conversation and message CRUD operations
- citations: Citation parsing from assistant responses
- suggestions: Follow-up suggestion generation
- tool_executor: Generalized streaming tool-calling loop
- grant_assistant: Grant Discovery Assistant scope configuration (Phase 3)
- tools/: Tool handler functions for the grant assistant
"""

from app.chat.sse import sse_event, sse_token, sse_error, sse_progress, sse_done
from app.chat.citations import parse_citations
from app.chat.conversations import (
    get_or_create_conversation,
    store_message,
    get_conversation_history,
    update_conversation_timestamp,
)
from app.chat.prompts import (
    build_system_prompt,
    build_wizard_system_prompt,
)
from app.chat.suggestions import (
    generate_suggestions_internal,
    generate_scope_suggestions,
    generate_smart_suggestions,
)

__all__ = [
    # SSE helpers
    "sse_event",
    "sse_token",
    "sse_error",
    "sse_progress",
    "sse_done",
    # Citations
    "parse_citations",
    # Conversations
    "get_or_create_conversation",
    "store_message",
    "get_conversation_history",
    "update_conversation_timestamp",
    # Prompts
    "build_system_prompt",
    "build_wizard_system_prompt",
    # Suggestions
    "generate_suggestions_internal",
    "generate_scope_suggestions",
    "generate_smart_suggestions",
]
