"""Persistent shell session implementation for cross-platform support."""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .security import DirectExecutor, PolicyViolationError, SecurityPolicy, ShellExecutor

logger = logging.getLogger(__name__)

# Marker for command completion detection
_DONE_MARKER_PREFIX = "__SHELL_CMD_DONE__"


@dataclass(frozen=True)
class CommandResult:
    """Result from executing a shell command."""

    output: str
    exit_code: Optional[int]
    timed_out: bool
    truncated_by_lines: bool
    truncated_by_bytes: bool
    duration: float
    blocked: bool = False


class PersistentShellSession:
    """
    Persistent shell session that maintains state across commands.

    Supports Windows (cmd, powershell) and Unix (bash) shells.
    Commands are executed sequentially in the same session, preserving
    working directory, environment variables, and other shell state.
    """

    def __init__(
        self,
        workspace: Path,
        shell_command: list[str],
        environment: Dict[str, str],
        command_timeout: float,
        startup_timeout: float,
        max_output_lines: int,
        max_output_bytes: int,
        *,
        executor: ShellExecutor | None = None,
        policy: SecurityPolicy | None = None,
    ) -> None:
        """
        Initialize persistent shell session.

        Args:
            workspace: Working directory for shell
            shell_command: Command to start shell process
            environment: Environment variables (overrides)
            command_timeout: Timeout for command execution
            startup_timeout: Timeout for shell startup
            max_output_lines: Maximum output lines
            max_output_bytes: Maximum output bytes
            executor: Optional executor implementation (defaults to DirectExecutor)
            policy: Optional command filtering policy
        """
        self._workspace = workspace
        self._shell_command = list(shell_command)
        self._command_timeout = command_timeout
        self._startup_timeout = startup_timeout
        self._max_output_lines = max_output_lines
        self._max_output_bytes = max_output_bytes
        self._policy = policy
        self._is_windows = os.name == "nt"

        merged_environment = dict(os.environ)
        merged_environment.update(environment)

        if executor is None:
            effective_environment = (
                policy.filter_environment(merged_environment)
                if policy is not None
                else merged_environment
            )
            self._executor = DirectExecutor(
                shell_command=self._shell_command,
                workspace=self._workspace,
                environment=effective_environment,
            )
            self._environment = dict(effective_environment)
        else:
            self._executor = executor
            self._environment = dict(merged_environment)

    @property
    def workspace(self) -> Path:
        """Return the configured workspace path."""
        return self._workspace

    def start(self) -> None:
        """Start the shell executor."""
        if self._executor.is_alive():
            logger.debug("Shell session already running")
            return

        logger.info(
            "Starting shell session via %s executor: %s",
            self._executor.executor_type,
            " ".join(self._shell_command),
        )
        self._executor.start()

    def execute(
        self,
        command: str,
        *,
        enforce_policy: bool = True,
        timeout_override: float | None = None,
    ) -> CommandResult:
        """
        Execute a command in the persistent shell.

        Args:
            command: Command string to execute
            enforce_policy: Whether to apply command security policy
            timeout_override: Optional per-call timeout override in seconds

        Returns:
            CommandResult with output and metadata
        """
        if not self._executor.is_alive():
            raise RuntimeError("Shell session is not running")

        if not command or not command.strip():
            return CommandResult(
                output="",
                exit_code=0,
                timed_out=False,
                truncated_by_lines=False,
                truncated_by_bytes=False,
                duration=0.0,
            )

        if enforce_policy and self._policy is not None:
            try:
                self._policy.validate(command)
            except PolicyViolationError as exc:
                logger.info("Command blocked by security policy: %s", exc)
                return CommandResult(
                    output=str(exc),
                    exit_code=None,
                    timed_out=False,
                    truncated_by_lines=False,
                    truncated_by_bytes=False,
                    duration=0.0,
                    blocked=True,
                )

        # Generate unique marker for this command
        marker = f"{_DONE_MARKER_PREFIX}_{uuid.uuid4().hex}"

        # Construct command with marker
        if self._is_windows:
            # Windows: use echo and errorlevel
            full_command = f"{command}\necho {marker} %ERRORLEVEL%\n"
        else:
            # Unix: use echo and $?
            full_command = f"{command}\necho {marker} $?\n"

        effective_timeout = (
            float(timeout_override)
            if isinstance(timeout_override, (int, float)) and timeout_override > 0
            else self._command_timeout
        )

        start_time = time.perf_counter()

        try:
            # Send command to shell
            self._executor.send_command(full_command)

            # Collect output until marker appears
            output_lines: list[str] = []
            stderr_lines: list[str] = []
            exit_code: Optional[int] = None
            total_bytes = 0
            truncated_by_lines = False
            truncated_by_bytes = False
            timed_out = False

            deadline = start_time + effective_timeout

            while True:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    logger.warning("Command timed out after %s seconds", effective_timeout)
                    break

                line_item = self._executor.read_output(timeout=min(remaining, 0.1))
                if line_item is None:
                    # Check if process died
                    if not self._executor.is_alive():
                        logger.warning("Shell process terminated unexpectedly")
                        break
                    continue

                stream_name, line = line_item

                # Check for completion marker
                if marker in line:
                    # Extract exit code
                    parts = line.split(marker)
                    if len(parts) > 1:
                        try:
                            exit_code = int(parts[1].strip())
                        except ValueError:
                            exit_code = None
                    break

                # Collect output
                if stream_name == "stdout":
                    output_lines.append(line.rstrip("\r\n"))
                else:
                    stderr_lines.append(line.rstrip("\r\n"))

                # Check size limits
                total_bytes += len(line.encode("utf-8"))
                if total_bytes > self._max_output_bytes:
                    truncated_by_bytes = True
                    logger.debug("Output truncated by bytes limit")
                    break

                if len(output_lines) + len(stderr_lines) > self._max_output_lines:
                    truncated_by_lines = True
                    logger.debug("Output truncated by lines limit")
                    break

            duration = time.perf_counter() - start_time

            # If we exited before seeing the completion marker, buffered output from the
            # unfinished command may pollute the next command. Reset the session so the
            # middleware can create a fresh shell on the next tool call.
            if (timed_out or truncated_by_lines or truncated_by_bytes) and self.is_alive():
                logger.warning(
                    "Resetting shell session after incomplete command "
                    "(timeout=%s, truncated_lines=%s, truncated_bytes=%s)",
                    timed_out,
                    truncated_by_lines,
                    truncated_by_bytes,
                )
                try:
                    self.stop(timeout=1.0)
                except Exception as exc:  # pragma: no cover - defensive cleanup
                    logger.warning("Failed to reset shell session after incomplete command: %s", exc)

            # Combine stdout and stderr
            all_output = output_lines + stderr_lines
            output_text = "\n".join(all_output)

            if truncated_by_bytes:
                output_text += f"\n... (output truncated at {self._max_output_bytes} bytes)"
            elif truncated_by_lines:
                output_text += f"\n... (output truncated at {self._max_output_lines} lines)"

            if timed_out:
                output_text += f"\n... (command timed out after {effective_timeout} seconds)"

            return CommandResult(
                output=output_text,
                exit_code=exit_code,
                timed_out=timed_out,
                truncated_by_lines=truncated_by_lines,
                truncated_by_bytes=truncated_by_bytes,
                duration=duration,
            )

        except Exception as exc:
            duration = time.perf_counter() - start_time
            logger.error("Command execution failed: %s", exc)
            return CommandResult(
                output=f"Error executing command: {exc}",
                exit_code=None,
                timed_out=False,
                truncated_by_lines=False,
                truncated_by_bytes=False,
                duration=duration,
            )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the shell session gracefully.

        Args:
            timeout: Timeout for graceful termination
        """
        self._executor.stop(timeout=timeout)

    def is_alive(self) -> bool:
        """Check if shell session is running."""
        return self._executor.is_alive()
