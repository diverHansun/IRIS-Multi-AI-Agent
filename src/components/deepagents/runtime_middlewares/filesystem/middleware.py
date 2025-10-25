from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, ModelRequest, ModelResponse
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from .tools import FILESYSTEM_TOOL_NAMES, FilesystemToolFactory, get_filesystem_tools
from .types import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    EMPTY_CONTENT_WARNING,
    MEMORIES_PREFIX,
    MAX_FILE_LINES,
    MAX_FILE_SIZE,
    FilesystemOptions,
    FilesystemSecurity,
    FilesystemState,
)
from .utils import format_with_line_numbers, string_to_file_data

BASE_PROMPT = """You can interact with a sandboxed in-memory filesystem using dedicated tools.

Key principles:
- Never assume access to the host machine; only work with the sandboxed files you create or read.
- Prefer listing files before reading or editing.
- Respect security restrictions when reading, writing, or editing files."""

LONG_TERM_PROMPT = f"""Long-term storage is available. Files saved there must be prefixed with '{MEMORIES_PREFIX}' when using the tools. Use it to preserve information across interactions."""

EVICTION_DIRECTORY = "/workspace/tool_results"


class FilesystemMiddleware(AgentMiddleware):
    """Middleware that exposes a managed virtual filesystem to the agent."""

    def __init__(
        self,
        *,
        long_term_memory: bool = False,
        allowed_paths: Optional[Iterable[str]] = None,
        excluded_paths: Optional[Iterable[str]] = None,
        excluded_extensions: Optional[Iterable[str]] = None,
        max_file_size: Optional[int] = None,
        max_file_lines: Optional[int] = None,
        tool_token_limit_before_evict: Optional[int] = None,
        tool_descriptions: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__()
        security = FilesystemSecurity(
            allowed_paths=list(allowed_paths or []),
            excluded_paths=list(excluded_paths or []),
            excluded_extensions=list(excluded_extensions or []),
            max_file_size=max_file_size or MAX_FILE_SIZE,
            max_file_lines=max_file_lines or MAX_FILE_LINES,
        )
        self.options = FilesystemOptions(
            long_term_memory=long_term_memory,
            tool_token_limit_before_evict=tool_token_limit_before_evict,
            security=security,
        )
        self.tools = get_filesystem_tools(options=self.options, descriptions=tool_descriptions)
        self._tool_name_cache = {tool.name for tool in self.tools}
        self.system_prompt = self._build_system_prompt()

    # ------------------------------------------------------------------ tool helpers
    def get_tools(self) -> List[Any]:
        """Return the filesystem tools for registration with the agent runtime."""
        return list(self.tools)

    def _build_system_prompt(self) -> str:
        lines = [BASE_PROMPT]
        allowed = list(self.options.security.allowed_paths)
        excluded = list(self.options.security.excluded_paths)
        if allowed:
            lines.append(f"Allowed paths: {', '.join(sorted(allowed))}.")
        if excluded:
            lines.append(f"Restricted paths: {', '.join(sorted(excluded))}.")
        if self.options.long_term_memory:
            lines.append(LONG_TERM_PROMPT)
        return "\n".join(lines)

    # ------------------------------------------------------------------ AgentMiddleware overrides
    def before_agent(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> Dict[str, Any] | None:
        if self.options.long_term_memory and runtime.store is None:
            raise ValueError("Long-term filesystem requested but runtime store is not configured")
        return None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
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
        result = handler(request)
        return self._maybe_evict_large_result(request.tool_call["name"], result)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ):
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
        safe_id = tool_call_id or uuid.uuid4().hex
        file_path = self._eviction_path(safe_id)
        try:
            file_data = string_to_file_data(payload, security=self.options.security)
        except ValueError as exc:
            warning = ToolMessage(
                (
                    "Tool output exceeded the configured filesystem limits and could not be persisted. "
                    f"Please tighten the output or increase the limits. Details: {exc}"
                ),
                tool_call_id=safe_id,
            )
            return {"messages": [warning]}

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
        return {
            "long_term_memory": self.options.long_term_memory,
            "tool_token_limit_before_evict": self.options.tool_token_limit_before_evict,
            "security": {
                "allowed_paths": list(self.options.security.allowed_paths),
                "excluded_paths": list(self.options.security.excluded_paths),
                "excluded_extensions": list(self.options.security.excluded_extensions),
                "max_file_size": self.options.security.max_file_size,
                "max_file_lines": self.options.security.max_file_lines,
            },
        }
