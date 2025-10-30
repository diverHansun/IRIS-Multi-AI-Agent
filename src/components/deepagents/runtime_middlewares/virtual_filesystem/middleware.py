"""Virtual filesystem middleware for DeepAgents."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, ModelRequest, ModelResponse
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from .tools import VIRTUAL_FILESYSTEM_TOOL_NAMES, VirtualFilesystemToolFactory, get_virtual_filesystem_tools
from .types import (
    DEFAULT_READ_LIMIT,
    EMPTY_CONTENT_WARNING,
    MEMORIES_PREFIX,
    FilesystemState,
    VirtualFilesystemOptions,
)
from .utils import format_with_line_numbers, string_to_file_data

BASE_PROMPT = """You can interact with a sandboxed in-memory filesystem using dedicated tools.

Key principles:
- Never assume access to the host machine; only work with the sandboxed files you create or read.
- Prefer listing files before reading or editing.
- All file operations are safe and isolated from the host system."""

LONG_TERM_PROMPT = f"""Long-term storage is available. Files saved there must be prefixed with '{MEMORIES_PREFIX}' when using the tools. Use it to preserve information across interactions."""

EVICTION_DIRECTORY = "/workspace/tool_results"


class VirtualFilesystemMiddleware(AgentMiddleware):
    """Middleware that exposes a managed virtual filesystem to the agent.

    This is a complete rewrite that removes all security constraints since
    the virtual filesystem is isolated from the host machine.
    """

    state_schema = FilesystemState

    def __init__(
        self,
        *,
        long_term_memory: bool = False,
        tool_token_limit_before_evict: Optional[int] = None,
        tool_descriptions: Optional[Sequence[str]] = None,
    ) -> None:
        """Initialize virtual filesystem middleware.

        Args:
            long_term_memory: Enable long-term storage via LangGraph Store
            tool_token_limit_before_evict: Token threshold for evicting large tool results
            tool_descriptions: Optional custom descriptions for the 4 tools
        """
        super().__init__()
        self.options = VirtualFilesystemOptions(
            long_term_memory=long_term_memory,
            tool_token_limit_before_evict=tool_token_limit_before_evict,
        )
        self.tools = get_virtual_filesystem_tools(options=self.options, descriptions=tool_descriptions)
        self._tool_name_cache = {tool.name for tool in self.tools}
        self.system_prompt = self._build_system_prompt()

    # ------------------------------------------------------------------ tool helpers
    def get_tools(self) -> List[Any]:
        """Return the filesystem tools for registration with the agent runtime."""
        return list(self.tools)

    def _build_system_prompt(self) -> str:
        """Build system prompt for virtual filesystem.

        Much simpler than before - no security constraints to mention.
        """
        lines = [BASE_PROMPT]
        if self.options.long_term_memory:
            lines.append(LONG_TERM_PROMPT)
        return "\n".join(lines)

    # ------------------------------------------------------------------ AgentMiddleware overrides
    def before_agent(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> Dict[str, Any] | None:
        """Validate configuration before agent starts."""
        if self.options.long_term_memory and runtime.store is None:
            raise ValueError("Long-term filesystem requested but runtime store is not configured")
        return None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
        """Inject system prompt into model request."""
        if self.system_prompt:
            if request.system_prompt:
                request.system_prompt = f"{request.system_prompt}\n\n{self.system_prompt}"
            else:
                request.system_prompt = self.system_prompt
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ):
        """Async version of wrap_model_call."""
        if self.system_prompt:
            if request.system_prompt:
                request.system_prompt = f"{request.system_prompt}\n\n{self.system_prompt}"
            else:
                request.system_prompt = self.system_prompt
        return await handler(request)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command:
        """Intercept tool results for large result eviction."""
        result = handler(request)
        return self._maybe_evict_large_result(request.tool_call["name"], result)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ):
        """Async version of wrap_tool_call."""
        result = await handler(request)
        return self._maybe_evict_large_result(request.tool_call["name"], result)

    # ------------------------------------------------------------------ eviction handling
    def _eviction_threshold(self) -> Optional[int]:
        return self.options.tool_token_limit_before_evict

    def _should_evict(self, text: str) -> bool:
        threshold = self._eviction_threshold()
        if threshold is None:
            return False
        return len(text) > threshold * 4

    def _eviction_path(self, tool_call_id: str) -> str:
        return f"{EVICTION_DIRECTORY}/{tool_call_id}.txt"

    def _persist_tool_payload(self, tool_call_id: str, payload: str) -> Dict[str, Any]:
        """Save large tool result to virtual filesystem."""
        safe_id = tool_call_id or uuid.uuid4().hex
        file_path = self._eviction_path(safe_id)

        # No security checks needed - virtual filesystem is isolated
        file_data = string_to_file_data(payload)

        preview_lines = file_data["content"][:10]
        preview = format_with_line_numbers(preview_lines, style="tab", start_line=1) if preview_lines else EMPTY_CONTENT_WARNING
        message = ToolMessage(
            (
                f"Tool output was too large to include inline and was saved to {file_path}.\n"
                f"Preview:\n{preview}"
            ),
            tool_call_id=safe_id,
        )
        return {"files": {file_path: file_data}, "messages": [message]}

    def _merge_updates(self, original: Optional[Dict[str, Any]], additional: Dict[str, Any]) -> Dict[str, Any]:
        """Merge state updates."""
        merged: Dict[str, Any] = dict(original or {})
        files = dict(merged.get("files", {}))
        messages: List[BaseMessage] = list(merged.get("messages", []))
        files.update(additional.get("files", {}))
        messages.extend(additional.get("messages", []))
        merged["files"] = files
        if messages:
            merged["messages"] = messages
        return merged

    def _maybe_evict_large_result(
        self,
        tool_name: str,
        result: ToolMessage | Command,
    ) -> ToolMessage | Command:
        """Check if tool result should be evicted to virtual filesystem."""
        # Don't evict virtual filesystem tool results
        if tool_name in self._tool_name_cache:
            return result

        threshold = self._eviction_threshold()
        if threshold is None:
            return result

        if isinstance(result, ToolMessage) and isinstance(result.content, str) and self._should_evict(result.content):
            update = self._persist_tool_payload(result.tool_call_id or "", result.content)
            return Command(update=update)

        if isinstance(result, Command):
            update = result.update
            if not update:
                return result
            messages = update.get("messages")
            if not messages:
                return result

            new_messages: List[BaseMessage] = []
            aggregate_update: Optional[Dict[str, Any]] = None
            for message in messages:
                if isinstance(message, ToolMessage) and isinstance(message.content, str) and self._should_evict(message.content):
                    extra_update = self._persist_tool_payload(message.tool_call_id or "", message.content)
                    aggregate_update = self._merge_updates(aggregate_update, extra_update)
                else:
                    new_messages.append(message)

            if aggregate_update is None:
                return result

            merged = self._merge_updates(update, aggregate_update)
            merged["messages"] = new_messages + aggregate_update.get("messages", [])
            return Command(update=merged)

        return result

    # ------------------------------------------------------------------ metadata helpers
    def describe(self) -> Dict[str, Any]:
        """Return middleware configuration for debugging."""
        return {
            "long_term_memory": self.options.long_term_memory,
            "tool_token_limit_before_evict": self.options.tool_token_limit_before_evict,
        }
