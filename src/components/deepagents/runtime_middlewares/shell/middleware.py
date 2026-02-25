"""Shell tool middleware providing persistent shell sessions for agents."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, AgentState, PrivateStateAttr
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from langgraph.types import Command
from typing_extensions import Annotated, NotRequired

from .config import ShellConfig
from .session import PersistentShellSession
from .tool import ShellTool

logger = logging.getLogger(__name__)


class ShellToolState(AgentState):
    """Agent state extension for shell session resources."""

    shell_session: NotRequired[
        Annotated[Optional[PersistentShellSession], UntrackedValue, PrivateStateAttr]
    ]


class ShellToolMiddleware(AgentMiddleware[ShellToolState, Any]):
    """
    Middleware that provides a persistent shell tool for agents.

    This middleware creates and manages a long-lived shell session that:
    - Maintains state across command executions (working directory, environment)
    - Supports Windows (cmd, powershell) and Unix (bash) shells
    - Handles HITL interrupts by recreating the session on resume
    - Provides safe output truncation and timeout handling

    The shell session is created before the agent starts and cleaned up after
    it completes. The session handle is stored in agent state using UntrackedValue,
    so it is not checkpointed. On resume after HITL interrupt, the session is
    automatically recreated.
    """

    state_schema = ShellToolState

    def __init__(
        self,
        config: ShellConfig,
        tool_description: Optional[str] = None,
    ) -> None:
        """
        Initialize shell tool middleware.

        Args:
            config: Shell configuration
            tool_description: Optional override for tool description
        """
        super().__init__()
        self.config = config
        self._tool = ShellTool(middleware=self)

        # Override tool description if provided
        if tool_description:
            self._tool.description = tool_description

        self.tools = [self._tool]

        logger.info(
            "ShellToolMiddleware initialized (shell_type=%s, workspace=%s)",
            config.shell_type,
            config.workspace_root,
        )

    def get_tools(self) -> List[ShellTool]:
        """Return the shell tool."""
        return list(self.tools)

    def before_agent(
        self,
        state: ShellToolState,
        runtime: Runtime[Any],
    ) -> Dict[str, Any] | None:
        """
        Create shell session before agent starts.

        Args:
            state: Agent state
            runtime: Runtime instance

        Returns:
            State update with shell session
        """
        # Check if workspace exists
        if not self.config.workspace_root.exists():
            raise ValueError(
                f"Shell workspace does not exist: {self.config.workspace_root}"
            )
        if not self.config.workspace_root.is_dir():
            raise ValueError(
                f"Shell workspace is not a directory: {self.config.workspace_root}"
            )

        # Create or reuse session
        session = self._get_or_create_session(state)

        logger.info("Shell session ready for agent")
        return {"shell_session": session}

    async def abefore_agent(
        self,
        state: ShellToolState,
        runtime: Runtime[Any],
    ) -> Dict[str, Any] | None:
        """Async version of before_agent."""
        return self.before_agent(state, runtime)

    def after_agent(
        self,
        state: ShellToolState,
        runtime: Runtime[Any],
    ) -> None:
        """
        Clean up shell session after agent completes.

        Args:
            state: Agent state
            runtime: Runtime instance
        """
        session = state.get("shell_session")
        if session and isinstance(session, PersistentShellSession):
            try:
                session.stop(timeout=self.config.termination_timeout)
            except Exception as exc:
                logger.warning("Error stopping shell session: %s", exc)

        logger.info("Shell session cleaned up")

    async def aafter_agent(
        self,
        state: ShellToolState,
        runtime: Runtime[Any],
    ) -> None:
        """Async version of after_agent."""
        self.after_agent(state, runtime)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """
        Intercept shell tool calls and execute in persistent session.

        Args:
            request: Tool call request
            handler: Default handler (used for non-shell tools)

        Returns:
            Tool message with command result
        """
        if not isinstance(request.tool, ShellTool):
            return handler(request)

        return self._execute_shell_tool(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Async version of wrap_tool_call with proper awaiting semantics."""
        if isinstance(request.tool, ShellTool):
            return self._execute_shell_tool(request)

        return await handler(request)

    def _get_or_create_session(self, state: AgentState) -> PersistentShellSession:
        """
        Get existing session or create new one.

        This supports HITL resume by recreating the session if it doesn't exist.

        Args:
            state: Agent state

        Returns:
            PersistentShellSession instance
        """
        session = state.get("shell_session")

        # Check if session exists and is alive
        if session and isinstance(session, PersistentShellSession) and session.is_alive():
            return session

        # Create new session
        logger.info("Creating new shell session")

        shell_command = self.config.get_shell_command()
        new_session = PersistentShellSession(
            workspace=self.config.workspace_root,
            shell_command=shell_command,
            environment=self.config.environment,
            command_timeout=self.config.command_timeout,
            startup_timeout=self.config.startup_timeout,
            max_output_lines=self.config.max_output_lines,
            max_output_bytes=self.config.max_output_bytes,
        )

        new_session.start()

        # Run startup commands if configured
        if self.config.startup_commands:
            logger.info("Running %d startup commands", len(self.config.startup_commands))
            for cmd in self.config.startup_commands:
                try:
                    result = new_session.execute(cmd)
                    logger.debug("Startup command result: %s", result.output[:200])
                except Exception as exc:
                    logger.warning("Startup command failed: %s", exc)

        # Update state
        if isinstance(state, dict):
            state["shell_session"] = new_session

        return new_session

    def _execute_shell_tool(self, request: ToolCallRequest) -> ToolMessage:
        """Execute the shell tool and wrap the result in a ToolMessage."""
        session = self._get_or_create_session(request.state)

        args = request.tool_call.get("args", {}) or {}
        command = args.get("command", "")
        timeout_override = args.get("timeout")

        result = self._execute_command(session, command, timeout_override)
        tool_call_id = request.tool_call.get("id")
        return ToolMessage(
            content=result,
            tool_call_id=tool_call_id,
            name="shell",
        )

    def _execute_command(
        self,
        session: PersistentShellSession,
        command: str,
        timeout_override: Optional[float],
    ) -> Dict[str, Any]:
        """
        Execute command in session and format result.

        Args:
            session: Shell session
            command: Command to execute
            timeout_override: Optional timeout override

        Returns:
            Formatted result dictionary
        """
        if not command or not command.strip():
            return {
                "status": "error",
                "output": "",
                "error": "Command cannot be empty",
            }

        logger.info("Executing shell command: %s", command[:100])

        original_timeout = session._command_timeout
        try:
            # Apply timeout override if provided
            if timeout_override and timeout_override > 0:
                session._command_timeout = timeout_override

            try:
                result = session.execute(command)
            finally:
                session._command_timeout = original_timeout

            # Format result
            status = "success" if result.exit_code == 0 else "error"
            if result.timed_out:
                status = "timeout"

            response = {
                "status": status,
                "command": command,
                "output": result.output,
                "exit_code": result.exit_code,
                "duration": round(result.duration, 3),
            }

            if result.timed_out:
                response["timeout"] = True
            if result.truncated_by_lines or result.truncated_by_bytes:
                response["truncated"] = True

            logger.info(
                "Command completed (status=%s, exit_code=%s, duration=%.3fs)",
                status,
                result.exit_code,
                result.duration,
            )

            return response

        except Exception as exc:
            logger.error("Command execution failed: %s", exc)
            return {
                "status": "error",
                "command": command,
                "output": "",
                "error": f"Failed to execute command: {exc}",
            }

    def describe(self) -> Dict[str, Any]:
        """Return middleware configuration summary."""
        return {
            "enabled": self.config.enabled,
            "shell_type": self.config.shell_type,
            "workspace_root": str(self.config.workspace_root),
            "command_timeout": self.config.command_timeout,
            "max_output_lines": self.config.max_output_lines,
            "max_output_bytes": self.config.max_output_bytes,
            "tools": ["shell"],
        }
