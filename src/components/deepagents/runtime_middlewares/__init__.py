"""Custom middleware implementations used by the DeepAgents runtime.

These classes intentionally avoid importing the official `deepagents` package so that
we retain full control over prompting and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, ModelRequest, ModelResponse
from langchain_core.messages import RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

__all__ = [
    "FilesystemMiddleware",
    "PatchToolCallsMiddleware",
    "SubAgentMiddleware",
    "SubAgent",
    "CompiledSubAgent",
]


@dataclass(slots=True)
class SubAgent:
    """Lightweight spec used to describe a subagent to the orchestrator."""

    name: str
    description: str
    system_prompt: str
    tools: Sequence[Any] = field(default_factory=list)
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompiledSubAgent:
    """Placeholder for a fully compiled subagent runnable."""

    name: str
    description: str
    runnable: Any


class FilesystemMiddleware(AgentMiddleware):
    """Inject filesystem guardrails into the system prompt."""

    def __init__(
        self,
        *,
        long_term_memory: bool = False,
        allowed_paths: Optional[Iterable[str]] = None,
        excluded_paths: Optional[Iterable[str]] = None,
        tool_token_limit_before_evict: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.long_term_memory = long_term_memory
        self.allowed_paths = list(allowed_paths or [])
        self.excluded_paths = list(excluded_paths or [])
        self.tool_token_limit_before_evict = tool_token_limit_before_evict
        self.tools: List[Any] = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        lines = [
            "When interacting with the filesystem, use the provided tools responsibly.",
            "Never read or write outside the approved directories.",
        ]
        if self.allowed_paths:
            lines.append(f"Allowed paths: {', '.join(self.allowed_paths)}.")
        if self.excluded_paths:
            lines.append(f"Restricted paths: {', '.join(self.excluded_paths)}.")
        if self.long_term_memory:
            lines.append("Long-term memory persistence is enabled for authorised files.")
        return "\n".join(lines)

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return await handler(request)

    def describe(self) -> Dict[str, Any]:
        return {
            "long_term_memory": self.long_term_memory,
            "allowed_paths": self.allowed_paths,
            "excluded_paths": self.excluded_paths,
            "tool_token_limit_before_evict": self.tool_token_limit_before_evict,
        }


class PatchToolCallsMiddleware(AgentMiddleware):
    """Patch dangling tool calls to keep conversation history consistent."""

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state["messages"]
        if not messages:
            return None

        patched_messages = []
        for idx, msg in enumerate(messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    corresponding = next(
                        (
                            candidate
                            for candidate in messages[idx:]
                            if candidate.type == "tool" and candidate.tool_call_id == tool_call["id"]
                        ),
                        None,
                    )
                    if corresponding is None:
                        patched_messages.append(
                            ToolMessage(
                                content=(
                                    f"Tool call {tool_call['name']} with id {tool_call['id']} "
                                    "was cancelled before completion."
                                ),
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )

        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched_messages]}


class SubAgentMiddleware(AgentMiddleware):
    """Advertise available subagents and encourage deliberate delegation."""

    def __init__(
        self,
        *,
        default_model: str | Any,
        default_tools: Sequence[Any] | None = None,
        subagents: List[SubAgent | CompiledSubAgent] | None = None,
        default_middleware: Sequence[AgentMiddleware] | None = None,
        default_interrupt_on: Dict[str, Any] | None = None,
        general_purpose_agent: bool = True,
        task_description: str | None = None,
    ) -> None:
        super().__init__()
        self.default_model = default_model
        self.default_tools = list(default_tools or [])
        self.subagents = subagents or []
        self.default_middleware = list(default_middleware or [])
        self.default_interrupt_on = default_interrupt_on or {}
        self.general_purpose_agent = general_purpose_agent
        self.task_description = task_description or "Delegate complex or parallelisable work to subagents."
        self.tools: List[Any] = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        if not self.subagents:
            return ""

        lines = [
            "You can launch short-lived subagents to handle focused tasks.",
            self.task_description,
            "",
            "Available subagents:",
        ]
        for subagent in self.subagents:
            description = getattr(subagent, "description", "No description provided.")
            lines.append(f"- {subagent.name}: {description}")
        if self.general_purpose_agent:
            lines.append("- general-purpose: Mirrors your capabilities for isolated tasks.")
        return "\n".join(lines)

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return await handler(request)

    def describe(self) -> Dict[str, Any]:
        return {
            "subagents": [
                {
                    "name": subagent.name,
                    "description": getattr(subagent, "description", ""),
                    "model": getattr(subagent, "model", None),
                }
                for subagent in self.subagents
            ],
            "general_purpose_agent": self.general_purpose_agent,
        }
