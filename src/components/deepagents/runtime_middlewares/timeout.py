"""Execution timeout middleware for DeepAgents."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Annotated, Any

from langchain_core.messages import AIMessage
from langgraph.channels.untracked_value import UntrackedValue
from typing_extensions import NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    PrivateStateAttr,
    hook_config,
)

if TYPE_CHECKING:
    from langgraph.runtime import Runtime


class ExecutionTimeoutState(AgentState):
    """State schema for ExecutionTimeoutMiddleware.

    Extends AgentState with execution time tracking fields.
    """

    execution_start_time: NotRequired[Annotated[float, UntrackedValue, PrivateStateAttr]]


class ExecutionTimeoutError(Exception):
    """Exception raised when agent execution time limit is exceeded.

    This exception is raised when the configured max_execution_time
    has been exceeded during agent execution.
    """

    def __init__(self, elapsed_time: float, max_execution_time: float) -> None:
        """Initialize the exception with timing information.

        Args:
            elapsed_time: Actual elapsed time in seconds.
            max_execution_time: Maximum allowed execution time in seconds.
        """
        self.elapsed_time = elapsed_time
        self.max_execution_time = max_execution_time

        msg = (
            f"Execution time limit exceeded: {elapsed_time:.2f}s / {max_execution_time:.2f}s. "
            "The agent has been running longer than the configured maximum execution time."
        )
        super().__init__(msg)


class ExecutionTimeoutMiddleware(AgentMiddleware[ExecutionTimeoutState, Any]):
    """Middleware that tracks total execution time and enforces limits.

    This middleware monitors the total execution time of an agent from the start
    of execution and can terminate the agent when the specified time limit is reached.
    This is different from step_timeout which limits individual step execution time.

    The max_execution_time represents the total wall-clock time allowed for the
    entire agent execution, from before_agent to after_agent.

    Example:
        ```python
        from src.components.deepagents.middleware.timeout import ExecutionTimeoutMiddleware
        from langchain.agents import create_agent

        # Create middleware with 600 second (10 minute) limit
        timeout_middleware = ExecutionTimeoutMiddleware(max_execution_time=600)

        agent = create_agent("openai:gpt-4o", middleware=[timeout_middleware])

        # Agent will automatically jump to end when time limit is exceeded
        result = await agent.invoke({"messages": [HumanMessage("Long running task")]})
        ```
    """

    state_schema = ExecutionTimeoutState

    def __init__(self, max_execution_time: float) -> None:
        """Initialize the execution timeout middleware.

        Args:
            max_execution_time: Maximum total execution time allowed in seconds.
                Must be a positive number.

        Raises:
            ValueError: If max_execution_time is not positive.
        """
        super().__init__()

        if max_execution_time <= 0:
            msg = f"max_execution_time must be positive, got {max_execution_time}"
            raise ValueError(msg)

        self.max_execution_time = max_execution_time

    def before_agent(
        self, state: ExecutionTimeoutState, runtime: Runtime  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Record the start time when agent execution begins.

        Args:
            state: The current agent state.
            runtime: The langgraph runtime.

        Returns:
            State update with execution start time.
        """
        return {"execution_start_time": time.time()}

    @hook_config(can_jump_to=["end"])
    def before_model(
        self, state: ExecutionTimeoutState, runtime: Runtime  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Check if execution time limit has been exceeded before each model call.

        Args:
            state: The current agent state containing start time.
            runtime: The langgraph runtime.

        Returns:
            If time limit is exceeded, returns a Command to jump to the end
            with a timeout message. Otherwise returns None.

        Raises:
            ExecutionTimeoutError: If execution time limit is exceeded.
        """
        start_time = state.get("execution_start_time")

        # If no start time recorded, skip check (shouldn't happen normally)
        if start_time is None:
            return None

        elapsed_time = time.time() - start_time

        # Check if time limit has been exceeded
        if elapsed_time >= self.max_execution_time:
            # Create a message indicating the timeout
            timeout_message = (
                f"Agent execution timed out after {elapsed_time:.2f} seconds. "
                f"Maximum allowed execution time is {self.max_execution_time:.2f} seconds."
            )
            timeout_ai_message = AIMessage(content=timeout_message)

            return {"jump_to": "end", "messages": [timeout_ai_message]}

        return None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: ExecutionTimeoutState, runtime: Runtime  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Async version of before_model check.

        Args:
            state: The current agent state containing start time.
            runtime: The langgraph runtime.

        Returns:
            If time limit is exceeded, returns a Command to jump to the end
            with a timeout message. Otherwise returns None.
        """
        # Reuse sync implementation
        return self.before_model(state, runtime)
