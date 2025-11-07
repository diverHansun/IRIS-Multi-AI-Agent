"""Persistent shell session implementation for cross-platform support."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

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
    ) -> None:
        """
        Initialize persistent shell session.

        Args:
            workspace: Working directory for shell
            shell_command: Command to start shell process
            environment: Environment variables
            command_timeout: Timeout for command execution
            startup_timeout: Timeout for shell startup
            max_output_lines: Maximum output lines
            max_output_bytes: Maximum output bytes
        """
        self._workspace = workspace
        self._shell_command = shell_command
        self._environment = dict(os.environ)
        self._environment.update(environment)
        self._command_timeout = command_timeout
        self._startup_timeout = startup_timeout
        self._max_output_lines = max_output_lines
        self._max_output_bytes = max_output_bytes

        self._process: Optional[subprocess.Popen[str]] = None
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._terminated = False
        self._is_windows = os.name == "nt"

    def start(self) -> None:
        """Start the shell subprocess and reader threads."""
        if self._process and self._process.poll() is None:
            logger.debug("Shell session already running")
            return

        logger.info("Starting shell session: %s", " ".join(self._shell_command))

        try:
            self._process = subprocess.Popen(
                self._shell_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self._workspace),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self._environment,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to start shell process: {exc}") from exc

        if not self._process.stdin or not self._process.stdout or not self._process.stderr:
            raise RuntimeError("Shell process missing stdin/stdout/stderr")

        # Start reader threads
        self._stdout_thread = threading.Thread(
            target=self._read_stream,
            args=(self._process.stdout, "stdout"),
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stream,
            args=(self._process.stderr, "stderr"),
            daemon=True,
        )

        self._stdout_thread.start()
        self._stderr_thread.start()

        logger.info("Shell session started successfully (PID: %s)", self._process.pid)

    def _read_stream(self, stream: Any, stream_name: str) -> None:
        """Read from stream and put lines into queue."""
        try:
            for line in stream:
                if self._terminated:
                    break
                self._queue.put((stream_name, line))
        except Exception as exc:
            logger.debug("Stream reader thread error (%s): %s", stream_name, exc)
        finally:
            logger.debug("Stream reader thread exiting: %s", stream_name)

    def execute(self, command: str) -> CommandResult:
        """
        Execute a command in the persistent shell.

        Args:
            command: Command string to execute

        Returns:
            CommandResult with output and metadata
        """
        if not self._process or self._process.poll() is not None:
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

        # Generate unique marker for this command
        marker = f"{_DONE_MARKER_PREFIX}_{uuid.uuid4().hex}"

        # Construct command with marker
        if self._is_windows:
            # Windows: use echo and errorlevel
            full_command = f'{command}\necho {marker} %ERRORLEVEL%\n'
        else:
            # Unix: use echo and $?
            full_command = f'{command}\necho {marker} $?\n'

        start_time = time.perf_counter()

        try:
            # Send command to shell
            if not self._process.stdin:
                raise RuntimeError("Shell stdin is closed")

            self._process.stdin.write(full_command)
            self._process.stdin.flush()

            # Collect output until marker appears
            output_lines: list[str] = []
            stderr_lines: list[str] = []
            exit_code: Optional[int] = None
            total_bytes = 0
            truncated_by_lines = False
            truncated_by_bytes = False
            timed_out = False

            deadline = start_time + self._command_timeout

            while True:
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    timed_out = True
                    logger.warning("Command timed out after %s seconds", self._command_timeout)
                    break

                try:
                    stream_name, line = self._queue.get(timeout=min(remaining, 0.1))
                except queue.Empty:
                    # Check if process died
                    if self._process.poll() is not None:
                        logger.warning("Shell process terminated unexpectedly")
                        break
                    continue

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

            # Combine stdout and stderr
            all_output = output_lines + stderr_lines
            output_text = "\n".join(all_output)

            if truncated_by_bytes:
                output_text += f"\n... (output truncated at {self._max_output_bytes} bytes)"
            elif truncated_by_lines:
                output_text += f"\n... (output truncated at {self._max_output_lines} lines)"

            if timed_out:
                output_text += f"\n... (command timed out after {self._command_timeout} seconds)"

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
        if not self._process:
            return

        self._terminated = True

        try:
            # Try graceful termination first
            if self._process.poll() is None:
                if self._process.stdin:
                    try:
                        self._process.stdin.write("exit\n")
                        self._process.stdin.flush()
                    except Exception as exc:
                        logger.debug("Failed to send exit command: %s", exc)

                try:
                    self._process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    logger.warning("Shell did not exit gracefully, terminating")
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        logger.warning("Shell did not terminate, killing")
                        self._process.kill()

        except Exception as exc:
            logger.error("Error stopping shell session: %s", exc)
        finally:
            self._process = None
            logger.info("Shell session stopped")

    def is_alive(self) -> bool:
        """Check if shell session is running."""
        return self._process is not None and self._process.poll() is None
