"""Generalized streaming tool executor for Azure OpenAI function calling.

Handles:
- Streaming chunk accumulation with tool call detection
- Tool argument JSON parsing with error recovery
- Tool dispatch to registered handlers
- Re-streaming after tool calls (multi-round tool calling)
- Progress callbacks for SSE event emission
- Configurable max rounds to prevent infinite loops
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional, Union

from app.openai_provider import azure_openai_async_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stream event types
# ---------------------------------------------------------------------------


@dataclass
class TokenEvent:
    """A content token from the streaming LLM response."""

    content: str


@dataclass
class ToolCallStartEvent:
    """Emitted when a tool call is detected in the stream."""

    tool_name: str
    tool_id: str


@dataclass
class ToolCallResultEvent:
    """Emitted after a tool call has been executed."""

    tool_name: str
    tool_id: str
    result: dict


@dataclass
class CompletionEvent:
    """Emitted when the LLM has finished generating its response."""

    full_response: str
    tool_calls_made: list = field(default_factory=list)
    total_tokens: int = 0


StreamEvent = Union[
    TokenEvent, ToolCallStartEvent, ToolCallResultEvent, CompletionEvent
]

# Progress callback type: async fn(step, detail)
ProgressCallback = Callable[[str, str], Awaitable[None]]


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------


async def execute_streaming_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_handlers: dict[str, Callable] | None = None,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    max_tool_rounds: int = 5,
    on_progress: ProgressCallback | None = None,
    db=None,
    user_id: str | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Stream an LLM response with multi-round tool calling support.

    This generator yields :class:`StreamEvent` instances as the model
    streams tokens and invokes tools.  Tool handlers are dispatched via the
    *tool_handlers* dict which maps tool names to async callables.

    Each tool handler must accept ``(db, user_id, **kwargs)`` and return a
    dict.  For tools that do not need DB access the handler may simply
    ignore those parameters.

    Args:
        messages: The full messages array (system + history + user).
        tools: OpenAI-format tool definitions, or ``None`` to disable tools.
        tool_handlers: Mapping of tool names to async handler callables.
        model: Azure deployment name.  Falls back to the configured chat
               deployment when ``None``.
        temperature: Sampling temperature for the LLM.
        max_tokens: Maximum tokens for the LLM response.
        max_tool_rounds: Safety cap on the number of tool-calling rounds.
        on_progress: Optional async callback ``(step, detail)`` invoked
                     before/after tool execution for SSE progress events.
        db: Optional database session passed through to tool handlers.
        user_id: Optional user ID passed through to tool handlers.

    Yields:
        :class:`TokenEvent` for streamed content chunks,
        :class:`ToolCallStartEvent` when a tool invocation begins,
        :class:`ToolCallResultEvent` after each tool execution, and
        :class:`CompletionEvent` once the model finishes.
    """
    if model is None:
        # Lazy import to avoid circular dependency at module level
        from app.openai_provider import get_chat_deployment

        model = get_chat_deployment()

    tool_handlers = tool_handlers or {}
    messages = list(messages)  # Work on a copy to avoid mutating caller's list
    full_response = ""
    total_tokens = 0
    tool_calls_log: List[dict] = []
    tool_round = 0

    # Build kwargs for the API call
    api_kwargs: Dict[str, Any] = {}
    if tools:
        api_kwargs["tools"] = tools
        api_kwargs["tool_choice"] = "auto"

    stream = await azure_openai_async_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        **api_kwargs,
    )

    while True:
        accumulated_tool_calls: Dict[int, Dict[str, str]] = {}

        async for chunk in stream:
            if not chunk.choices:
                if hasattr(chunk, "usage") and chunk.usage:
                    total_tokens = getattr(chunk.usage, "total_tokens", 0)
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Handle content tokens (normal streaming)
            if delta.content:
                full_response += delta.content
                yield TokenEvent(content=delta.content)

            # Handle tool call chunks (accumulate arguments)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": (
                                tc.function.name
                                if tc.function and tc.function.name
                                else ""
                            ),
                            "arguments": "",
                        }
                    if tc.id:
                        accumulated_tool_calls[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        accumulated_tool_calls[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        accumulated_tool_calls[idx][
                            "arguments"
                        ] += tc.function.arguments

            # When the model finishes with tool_calls, execute them
            if finish_reason == "tool_calls" and accumulated_tool_calls:
                tool_round += 1
                tool_messages: List[Dict[str, Any]] = []
                restream_kwargs = dict(**api_kwargs)

                for t_idx in sorted(accumulated_tool_calls.keys()):
                    tc_data = accumulated_tool_calls[t_idx]
                    tool_name = tc_data["name"]
                    tool_id = tc_data["id"]

                    # Build the assistant tool_call message
                    tool_messages.append(
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": tc_data["arguments"],
                                    },
                                }
                            ],
                        }
                    )

                    # Check if we know how to handle this tool
                    if tool_name not in tool_handlers:
                        tool_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": f"Error: Unknown tool '{tool_name}'",
                            }
                        )
                        continue

                    # Enforce tool round limit
                    if tool_round > max_tool_rounds:
                        tool_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": (
                                    "Tool call limit reached for this message. "
                                    "Please answer using the information already available."
                                ),
                            }
                        )
                        restream_kwargs = {}  # Drop tools to prevent further attempts
                        continue

                    # Parse tool arguments with error recovery
                    try:
                        args = json.loads(tc_data["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        logger.warning(
                            "Failed to parse arguments for tool %s: %s",
                            tool_name,
                            tc_data.get("arguments", "")[:200],
                        )
                        tool_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_id,
                                "content": (
                                    "Error: Failed to parse tool arguments. "
                                    "Please try the tool call again with valid JSON arguments."
                                ),
                            }
                        )
                        continue

                    yield ToolCallStartEvent(tool_name=tool_name, tool_id=tool_id)

                    if on_progress:
                        await on_progress(
                            "tool_call",
                            f"Executing {tool_name}...",
                        )

                    # Dispatch to handler
                    try:
                        handler = tool_handlers[tool_name]
                        result = await handler(db=db, user_id=user_id, **args)
                    except Exception as exc:
                        logger.error(f"Tool handler {tool_name} failed: {exc}")
                        result = {"error": f"Tool execution failed: {exc}"}

                    tool_calls_log.append(
                        {
                            "name": tool_name,
                            "id": tool_id,
                            "args": args,
                            "result": result,
                        }
                    )

                    yield ToolCallResultEvent(
                        tool_name=tool_name,
                        tool_id=tool_id,
                        result=result,
                    )

                    # Format result as tool message for the model
                    result_content = (
                        result.get("content", "")
                        if isinstance(result, dict)
                        else str(result)
                    )
                    if not result_content and isinstance(result, dict):
                        result_content = json.dumps(result)

                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result_content,
                        }
                    )

                # Re-invoke the model with tool results
                if tool_messages:
                    messages.extend(tool_messages)

                    stream = await azure_openai_async_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **restream_kwargs,
                    )
                    break  # break async for -> re-enter while loop with new stream

            # Track usage if available
            if hasattr(chunk, "usage") and chunk.usage:
                total_tokens = getattr(chunk.usage, "total_tokens", 0)
        else:
            # async for completed without break -> stream exhausted normally
            break  # exit while loop

    yield CompletionEvent(
        full_response=full_response,
        tool_calls_made=tool_calls_log,
        total_tokens=total_tokens,
    )
