"""SubAgent middleware for delegating tasks to specialized agents.

This module implements the middleware that enables the main agent to delegate
tasks to specialized subagents, managing their lifecycle and integration.

Following SOLID principles:
- SRP: This module only handles subagent delegation middleware logic
- OCP: Extensible through configuration without modifying code
- DIP: Depends on abstractions (AgentMiddleware, SubAgent specs)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.runtime import Runtime
from langgraph.types import Command

from .types import SubAgent, CompiledSubAgent
from ..virtual_filesystem.types import FilesystemState

logger = logging.getLogger(__name__)

# State keys that should be excluded when passing state to subagents
# Following official DeepAgents implementation pattern
_EXCLUDED_STATE_KEYS = ("messages", "todos")


def _prepare_subagent_state(
    runtime: ToolRuntime[None, FilesystemState],
    description: str
) -> dict:
    """Prepare subagent state by copying all state except excluded keys.

    This function implements the state copying pattern from official DeepAgents,
    enabling virtual filesystem sharing between main agent and subagents.

    Args:
        runtime: Tool runtime context containing current agent state
        description: Task description to be sent as initial message to subagent

    Returns:
        Dictionary containing copied state with new messages list

    Design principles applied:
    - SRP: Single responsibility of preparing subagent state
    - DRY: Reuses FilesystemState's reducer for merging (no duplication)
    """
    # Copy all state except messages and todos (SOLID-OCP: extensible pattern)
    subagent_state = {
        k: v for k, v in runtime.state.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # Create new messages list with task description
    subagent_state["messages"] = [{"role": "user", "content": description}]

    # Debug logging for transparency
    logger.debug(
        f"[SubAgent] Prepared state with keys: {list(subagent_state.keys())}, "
        f"files count: {len(subagent_state.get('files', {}))}"
    )

    return subagent_state


def _return_state_update(
    result: dict,
    tool_call_id: str
) -> Command:
    """Return Command object with state updates from subagent execution.

    This function extracts state changes from subagent result and packages them
    into a Command object for LangGraph to merge using the registered reducers.

    Args:
        result: Subagent execution result containing state updates
        tool_call_id: Tool call ID for the ToolMessage

    Returns:
        Command object containing state updates and response message

    Design principles applied:
    - SRP: Single responsibility of packaging state updates
    - DRY: Relies on existing _file_data_reducer for actual merging
    """
    # Extract state updates, excluding messages and todos
    state_update = {
        k: v for k, v in result.items()
        if k not in _EXCLUDED_STATE_KEYS
    }

    # Extract response message from subagent
    messages = result.get("messages", [])
    response_text = ""
    if messages:
        last_msg = messages[-1]
        response_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    # Debug logging for transparency
    logger.debug(
        f"[SubAgent] State update keys: {list(state_update.keys())}, "
        f"files count: {len(state_update.get('files', {}))}"
    )

    # Return Command with state updates (files will be merged by reducer)
    return Command(
        update={
            **state_update,
            "messages": [{"role": "tool", "content": response_text, "tool_call_id": tool_call_id}],
        }
    )


class SubAgentMiddleware(AgentMiddleware):
    """Advertise available subagents and encourage deliberate delegation.

    This middleware manages the integration of specialized subagents into the
    main agent runtime, including:
    - Building system prompts that advertise available subagents
    - Creating task delegation tools
    - Managing subagent lifecycle and invocation

    The middleware follows the middleware pattern to inject subagent capabilities
    without modifying the core agent logic.
    """

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
        """Initialize SubAgentMiddleware.

        Args:
            default_model: Default model to use for subagents
            default_tools: Default tools available to subagents
            subagents: List of subagent specifications
            default_middleware: Default middleware to apply to all subagents
            default_interrupt_on: Default interrupt configuration
            general_purpose_agent: Whether to include a general-purpose agent
            task_description: Description of when to use subagents
        """
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
        """Build system prompt advertising available subagents.

        Returns:
            System prompt text describing available subagents
        """
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
        """Wrap synchronous model calls to inject subagent system prompt.

        Args:
            request: Model request to modify
            handler: Next handler in the middleware chain

        Returns:
            Model response from the handler
        """
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """Wrap asynchronous model calls to inject subagent system prompt.

        Args:
            request: Model request to modify
            handler: Next handler in the middleware chain

        Returns:
            Model response from the handler
        """
        if self.system_prompt:
            request.system_prompt = (
                f"{request.system_prompt}\n\n{self.system_prompt}"
                if request.system_prompt
                else self.system_prompt
            )
        return await handler(request)

    def _create_subagent_runnables(self) -> None:
        """Create runnable instances for each subagent using langchain.agents.create_agent.

        This method compiles each subagent specification into a runnable agent instance,
        applying the appropriate configuration, tools, and middleware.
        """
        from langchain.agents import create_agent

        for subagent_spec in self.subagents:
            if isinstance(subagent_spec, CompiledSubAgent):
                # Already compiled, use directly
                self._subagent_runnables[subagent_spec.name] = subagent_spec.runnable
            else:
                # Create agent from SubAgent spec
                subagent_model = subagent_spec.model if subagent_spec.model else self.default_model

                # Use configured tools, filtering from defaults if specified
                custom_tool_names = subagent_spec.tools if subagent_spec.tools else []
                if custom_tool_names:
                    # Filter default_tools to only include tools specified in custom_tool_names
                    subagent_tools = [
                        tool
                        for tool in self.default_tools
                        if (hasattr(tool, 'name') and tool.name in custom_tool_names) or
                           (hasattr(tool, '__name__') and tool.__name__ in custom_tool_names)
                    ]
                else:
                    # Use all default tools if no custom tools are specified
                    subagent_tools = self.default_tools

                # Use configured middleware (default middleware before custom)
                custom_middleware = list(subagent_spec.middleware) if subagent_spec.middleware else []
                combined_middleware = [*self.default_middleware, *custom_middleware]

                # Add ExecutionTimeoutMiddleware if max_execution_time is specified
                if hasattr(subagent_spec, 'max_execution_time') and subagent_spec.max_execution_time:
                    from ..timeout import ExecutionTimeoutMiddleware

                    timeout_middleware = ExecutionTimeoutMiddleware(
                        max_execution_time=subagent_spec.max_execution_time
                    )
                    # Insert at the beginning to ensure timeout is checked first
                    combined_middleware.insert(0, timeout_middleware)

                # Use configured checkpointer (respect config setting)
                checkpointer = subagent_spec.checkpointer if hasattr(subagent_spec, 'checkpointer') else False

                logger.debug(
                    f"SubAgent '{subagent_spec.name}' configuration: "
                    f"custom_tools={len(custom_tool_names)}, "
                    f"total_tools={len(subagent_tools)}, "
                    f"custom_middleware={len(custom_middleware)}, "
                    f"total_middleware={len(combined_middleware)}, "
                    f"max_execution_time={subagent_spec.max_execution_time if hasattr(subagent_spec, 'max_execution_time') else None}, "
                    f"checkpointer={checkpointer}"
                )

                # Create the subagent
                subagent_runnable = create_agent(
                    subagent_model,
                    system_prompt=subagent_spec.system_prompt,
                    tools=subagent_tools,
                    middleware=combined_middleware,
                    checkpointer=checkpointer,
                )

                # Apply runtime limits if specified
                if subagent_spec.recursion_limit:
                    subagent_runnable = subagent_runnable.with_config(
                        {"recursion_limit": subagent_spec.recursion_limit}
                    )
                    logger.debug(
                        f"SubAgent '{subagent_spec.name}' configured with recursion_limit={subagent_spec.recursion_limit}"
                    )
                if subagent_spec.step_timeout:
                    subagent_runnable.step_timeout = subagent_spec.step_timeout
                    logger.debug(
                        f"SubAgent '{subagent_spec.name}' configured with step_timeout={subagent_spec.step_timeout}"
                    )

                self._subagent_runnables[subagent_spec.name] = subagent_runnable

    def get_task_tool(self) -> Any | None:
        """Create and return the task tool for subagent delegation with state sharing.

        This method creates a task tool using the @tool decorator pattern, which
        enables automatic ToolRuntime injection for state sharing between main
        agent and subagents.

        Returns:
            Task tool instance or None if no subagents available

        Design principles applied:
        - KISS: Uses @tool decorator instead of StructuredTool for simplicity
        - SRP: Delegates state preparation and merging to helper functions
        - DRY: Reuses virtual filesystem's existing reducer mechanism
        """
        if not self._subagent_runnables:
            return None

        # Save reference to self for use in closure (KISS: simple pattern)
        middleware_self = self

        # Build available types list for tool description
        available_types = ", ".join(self._subagent_runnables.keys())

        @tool
        async def task(
            subagent_type: str,
            description: str,
            runtime: ToolRuntime[None, FilesystemState],
        ) -> str | Command:
            """Delegate complex tasks to specialized subagents.

            This tool enables the main agent to delegate tasks to specialized subagents.
            State (including virtual filesystem) is automatically shared between agents.

            Args:
                subagent_type: Type of subagent to use. Available types: {available_types}
                description: Detailed task description for the subagent
                runtime: Runtime context (automatically injected, not visible to LLM)

            Returns:
                Result from subagent execution, either as text or Command with state updates
            """
            # Validate subagent type
            if subagent_type not in middleware_self._subagent_runnables:
                error_msg = (
                    f"Error: Unknown subagent type '{subagent_type}'. "
                    f"Available: {list(middleware_self._subagent_runnables.keys())}"
                )
                logger.warning(error_msg)
                return error_msg

            # Log delegation
            logger.info(f"[SubAgent] Main agent delegating task to '{subagent_type}' subagent")
            logger.debug(f"[SubAgent] Task description: {description[:100]}...")

            subagent = middleware_self._subagent_runnables[subagent_type]

            try:
                # Step 1: Prepare state - copy files, exclude messages/todos (DRY principle)
                subagent_state = _prepare_subagent_state(runtime, description)

                # Step 2: Execute subagent with copied state
                result = await subagent.ainvoke(subagent_state)

                logger.info(f"[SubAgent] '{subagent_type}' completed successfully")

                # Step 3: Return Command for state merging
                if not runtime.tool_call_id:
                    # Graceful degradation: return text if no tool_call_id (KISS: simple fallback)
                    logger.warning(
                        f"[SubAgent] No tool_call_id available, "
                        "state updates will not be merged"
                    )
                    messages = result.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        return last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                    return "SubAgent completed but returned no response."

                # Return Command with state updates (SRP: delegate to helper function)
                return _return_state_update(result, runtime.tool_call_id)

            except TimeoutError as exc:
                # SubAgent step timeout - provide actionable feedback
                error_msg = (
                    f"[TIMEOUT] SubAgent '{subagent_type}' execution timed out.\n\n"
                    f"Possible causes:\n"
                    f"- Complex task requiring more time\n"
                    f"- Slow API response\n"
                    f"- Network issues\n\n"
                    f"Suggestions:\n"
                    f"- Break the task into smaller steps\n"
                    f"- Retry the operation\n"
                    f"- Use a different approach"
                )
                logger.warning(f"[SubAgent] '{subagent_type}' timed out: {exc}")
                return error_msg
            except Exception as exc:
                error_msg = f"SubAgent execution failed: {exc}"
                logger.error(f"[SubAgent] '{subagent_type}' failed: {exc}", exc_info=True)
                return error_msg

        # Update docstring with available types
        task.__doc__ = task.__doc__.format(available_types=available_types)

        return task

    def describe(self) -> Dict[str, Any]:
        """Return metadata describing the middleware configuration.

        Returns:
            Dictionary containing middleware metadata
        """
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
