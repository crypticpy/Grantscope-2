"""Server-Sent Events formatting utilities for the chat service.

All SSE events follow the format: data: {json}\\n\\n
Event types: token, progress, citation, metadata, suggestions, done, error
"""

import json
from typing import Any


def sse_event(event_type: str, data: Any) -> str:
    """Format a generic Server-Sent Event.

    Returns a JSON payload with ``type`` and either ``content`` (for token
    events) or ``data`` (for all other event types).
    """
    if event_type == "token":
        payload = {"type": event_type, "content": data}
    else:
        payload = {"type": event_type, "data": data}
    return f"data: {json.dumps(payload)}\n\n"


def sse_token(content: str) -> str:
    """Format a streaming content token event."""
    return f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"


def sse_error(message: str) -> str:
    """Format an error event."""
    return f"data: {json.dumps({'type': 'error', 'content': message})}\n\n"


def sse_progress(step: str, detail: str) -> str:
    """Format a progress update event.

    Use this to inform the client about long-running operations such as
    tool execution or document retrieval.
    """
    return f"data: {json.dumps({'type': 'progress', 'data': {'step': step, 'detail': detail}})}\n\n"


def sse_done(conversation_id: str, message_id: str) -> str:
    """Format a stream-completion event.

    Signals that the assistant has finished generating its response.
    """
    return f"data: {json.dumps({'type': 'done', 'data': {'conversation_id': conversation_id, 'message_id': message_id}})}\n\n"


def sse_citation(citation_data: dict) -> str:
    """Format a citation event.

    ``citation_data`` should contain at minimum ``title`` and ``url`` keys.
    """
    return f"data: {json.dumps({'type': 'citation', 'data': citation_data})}\n\n"


def sse_metadata(metadata: dict) -> str:
    """Format a metadata event.

    Used to send auxiliary information about the response (e.g. model name,
    token usage, scope) outside of the main content stream.
    """
    return f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"


def sse_suggestions(suggestions: list[str]) -> str:
    """Format a follow-up suggestions event.

    ``suggestions`` is a list of short natural-language prompts the user
    can click to continue the conversation.
    """
    return f"data: {json.dumps({'type': 'suggestions', 'data': suggestions})}\n\n"


def sse_tool_result(tool_name: str, result: dict) -> str:
    """Format a tool result event.

    Sends structured tool call results to the frontend so it can render
    rich UI components (e.g. GrantResultCard) for search results.

    Args:
        tool_name: The name of the tool that produced the result.
        result: The tool's return value (typically contains a ``results`` list).
    """
    return f"data: {json.dumps({'type': 'tool_result', 'data': {'tool_name': tool_name, 'result': result}})}\n\n"
