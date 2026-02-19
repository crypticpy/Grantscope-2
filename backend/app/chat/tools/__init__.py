"""Grant assistant tool definitions and registry.

Provides a ToolDefinition dataclass and ToolRegistry for managing
the set of tools available to the grant discovery assistant.

Each tool module in this package registers its tools at import time.
The registry filters tools at runtime based on admin settings
(e.g., online_search_enabled).

Usage:
    from app.chat.tools import registry
    tools = registry.get_openai_definitions(online_enabled=True)
    handler = registry.get_handler("search_internal_grants")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List

logger = logging.getLogger(__name__)

# Type alias for async tool handler functions.
# All handlers must accept (db, user_id, **kwargs) and return a dict.
ToolHandler = Callable[..., Coroutine[Any, Any, dict]]


@dataclass
class ToolDefinition:
    """Describes a single tool available to the grant discovery assistant.

    Attributes:
        name: Unique tool name used in OpenAI function-calling.
        description: Human-readable description shown to the model.
        parameters: JSON Schema dict describing accepted arguments.
        handler: Async callable implementing the tool logic.
        requires_online: If True the tool needs external network access
            and will be excluded when online search is disabled.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    requires_online: bool = field(default=False)


class ToolRegistry:
    """Central registry of tool definitions for the grant assistant.

    Tools register themselves at import time by calling
    ``registry.register(tool_def)``.  At runtime the orchestrator
    queries the registry to build the OpenAI function-calling payload
    and to dispatch incoming tool calls to the correct handler.
    """

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition.

        Args:
            tool: The ToolDefinition to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                "Each tool name must be unique."
            )
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (online=%s)", tool.name, tool.requires_online)

    def get_openai_definitions(
        self, online_enabled: bool = False
    ) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI function-calling format.

        Args:
            online_enabled: When False, tools that require online access
                are excluded from the returned list.

        Returns:
            A list of dicts, each with ``{"type": "function", "function": {...}}``.
        """
        definitions: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            if tool.requires_online and not online_enabled:
                continue
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return definitions

    def get_handler(self, name: str) -> ToolHandler:
        """Look up the handler callable for a registered tool.

        Args:
            name: The tool name.

        Returns:
            The async handler callable.

        Raises:
            KeyError: If no tool with that name is registered.
        """
        if name not in self._tools:
            raise KeyError(
                f"No tool registered with name '{name}'. "
                f"Available tools: {list(self._tools.keys())}"
            )
        return self._tools[name].handler

    def has_tool(self, name: str) -> bool:
        """Check whether a tool with the given name is registered.

        Args:
            name: The tool name to check.

        Returns:
            True if the tool exists in the registry, False otherwise.
        """
        return name in self._tools

    def get_all_names(self, online_enabled: bool = False) -> List[str]:
        """Return the names of all registered tools.

        Args:
            online_enabled: When False, tools that require online access
                are excluded.

        Returns:
            A sorted list of tool name strings.
        """
        names: List[str] = []
        for tool in self._tools.values():
            if tool.requires_online and not online_enabled:
                continue
            names.append(tool.name)
        return sorted(names)


# Global singleton registry -- tool modules append to this on import.
registry = ToolRegistry()

# Import tool modules to trigger registration.  Each module calls
# ``registry.register(...)`` at module level.
from app.chat.tools import grant_search  # noqa: F401, E402
from app.chat.tools import grant_analysis  # noqa: F401, E402
from app.chat.tools import grant_actions  # noqa: F401, E402
from app.chat.tools import user_context  # noqa: F401, E402
