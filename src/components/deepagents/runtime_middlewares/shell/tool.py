"""Shell tool definition for agent use."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .middleware import ShellToolMiddleware


class ShellToolInput(BaseModel):
    """Input schema for shell tool."""

    command: str = Field(
        description="Shell command to execute in the persistent session"
    )
    timeout: Optional[float] = Field(
        default=None,
        description="Optional timeout override in seconds for this specific command",
    )


class ShellTool(BaseTool):
    """
    Tool for executing shell commands in a persistent session.

    This tool maintains shell state (working directory, environment variables)
    across multiple command executions. The actual execution is intercepted
    by the ShellToolMiddleware.
    """

    name: str = "shell"
    description: str = (
        "Execute a shell command in a persistent session. "
        "The session maintains state across commands (working directory, environment variables). "
        "Use this for running system commands, building projects, running tests, etc. "
        "Commands run from the configured workspace directory. "
        "For Windows, commands execute in cmd or powershell. For Linux/Mac, commands execute in bash. "
        "Chain commands with '&&' (run next if previous succeeds) or ';' (run next regardless). "
        "Avoid interactive commands that require user input. "
        "Long-running commands will be terminated after the configured timeout."
    )
    args_schema: type[BaseModel] = ShellToolInput

    middleware: Any = Field(exclude=True)

    def __init__(self, middleware: ShellToolMiddleware) -> None:
        """
        Initialize shell tool.

        Args:
            middleware: Parent middleware instance
        """
        super().__init__(middleware=middleware)

    def _run(self, command: str, timeout: Optional[float] = None, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute shell command.

        This method should not be called directly - execution is intercepted
        by the middleware's wrap_tool_call method.

        Args:
            command: Command to execute
            timeout: Optional timeout override
            **kwargs: Additional arguments

        Returns:
            Command execution result
        """
        raise RuntimeError(
            "Shell tool execution should be intercepted by middleware. "
            "This error indicates the middleware is not properly configured."
        )

    async def _arun(
        self, command: str, timeout: Optional[float] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Async version of _run.

        Args:
            command: Command to execute
            timeout: Optional timeout override
            **kwargs: Additional arguments

        Returns:
            Command execution result
        """
        return self._run(command, timeout, **kwargs)
