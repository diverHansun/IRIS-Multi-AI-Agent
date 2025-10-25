"""Custom middleware implementations used by the DeepAgents runtime.

These classes intentionally avoid importing the official `deepagents` package so that
we retain full control over prompting and configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, ModelRequest, ModelResponse
from langchain_core.messages import RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

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
        self._subagent_runnables: Dict[str, Any] = {}
        self._create_subagent_runnables()

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

    def _create_subagent_runnables(self) -> None:
        """Create runnable instances for each subagent using langchain.agents.create_agent."""
        from langchain.agents import create_agent

        for subagent_spec in self.subagents:
            if isinstance(subagent_spec, CompiledSubAgent):
                # Already compiled, use directly
                self._subagent_runnables[subagent_spec.name] = subagent_spec.runnable
            else:
                # Create agent from SubAgent spec
                subagent_model = subagent_spec.model if subagent_spec.model else self.default_model
                subagent_tools = list(subagent_spec.tools) if subagent_spec.tools else list(self.default_tools)

                # Create the subagent
                subagent_runnable = create_agent(
                    subagent_model,
                    system_prompt=subagent_spec.system_prompt,
                    tools=subagent_tools,
                    middleware=self.default_middleware,
                    checkpointer=False,
                )
                self._subagent_runnables[subagent_spec.name] = subagent_runnable

    def get_task_tool(self) -> Any | None:
        """Create and return the task tool for subagent delegation.

        This method should be called by the runtime builder to get the task tool
        before creating the agent, NOT dynamically added in middleware hooks.
        """
        if not self._subagent_runnables:
            return None

        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field

        class TaskInput(BaseModel):
            subagent_type: str = Field(description=f"Type of subagent to use. Options: {', '.join(self._subagent_runnables.keys())}")
            description: str = Field(description="Detailed task description for the subagent")

        async def invoke_task(subagent_type: str, description: str) -> str:
            """Invoke a subagent to handle a specific task."""
            if subagent_type not in self._subagent_runnables:
                error_msg = f"Error: Unknown subagent type '{subagent_type}'. Available: {list(self._subagent_runnables.keys())}"
                logger.warning(error_msg)
                return error_msg

            # Log subagent invocation
            logger.info(f"[SubAgent] Main agent delegating task to '{subagent_type}' subagent")
            logger.debug(f"[SubAgent] Task description: {description[:100]}...")

            subagent = self._subagent_runnables[subagent_type]
            try:
                result = await subagent.ainvoke({"messages": [{"role": "user", "content": description}]})
                # Extract the final message content
                messages = result.get("messages", [])
                if messages:
                    response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
                    logger.info(f"[SubAgent] '{subagent_type}' completed successfully")
                    return response
                logger.warning(f"[SubAgent] '{subagent_type}' completed but returned no response")
                return "SubAgent completed but returned no response."
            except Exception as exc:
                error_msg = f"SubAgent execution failed: {exc}"
                logger.error(f"[SubAgent] '{subagent_type}' failed: {exc}")
                return error_msg

        task_tool = StructuredTool(
            name="task",
            description=f"Delegate complex tasks to specialized subagents. Available types: {', '.join(self._subagent_runnables.keys())}",
            func=lambda **kwargs: None,  # Sync not supported
            coroutine=invoke_task,
            args_schema=TaskInput,
        )

        return task_tool

    def describe(self) -> Dict[str, Any]:
        return {
            "subagents": [
                {
                    "name": subagent.name if hasattr(subagent, 'name') else "unknown",
                    "description": getattr(subagent, "description", ""),
                    "model": getattr(subagent, "model", None),
                }
                for subagent in self.subagents
            ],
            "general_purpose_agent": self.general_purpose_agent,
            "subagent_count": len(self._subagent_runnables),
        }
