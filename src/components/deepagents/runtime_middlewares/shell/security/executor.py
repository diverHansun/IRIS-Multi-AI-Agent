"""Shell executor abstractions for persistent shell sessions."""

from __future__ import annotations

import logging
import queue
import subprocess
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ShellExecutor(ABC):
    """Abstract IO executor for a persistent shell session."""

    @abstractmethod
    def start(self) -> None:
        """Start the execution environment."""

    @abstractmethod
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the execution environment."""

    @abstractmethod
    def is_alive(self) -> bool:
        """Return True when the execution environment is running."""

    @abstractmethod
    def send_command(self, full_command: str) -> None:
        """Send a command string (including marker) to the environment."""

    @abstractmethod
    def read_output(self, timeout: float = 0.1) -> tuple[str, str] | None:
        """Read one output line from stdout/stderr, or None on timeout."""

    @property
    @abstractmethod
    def executor_type(self) -> str:
        """Executor type identifier."""


class DirectExecutor(ShellExecutor):
    """Direct host subprocess-backed shell executor."""

    def __init__(
        self,
        *,
        shell_command: list[str],
        workspace: Path,
        environment: dict[str, str],
    ) -> None:
        self._shell_command = list(shell_command)
        self._workspace = workspace
        self._environment = dict(environment)

        self._process: Optional[subprocess.Popen[str]] = None
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._terminated = False

    @property
    def executor_type(self) -> str:
        return "direct"

    def start(self) -> None:
        if self._process and self._process.poll() is None:
            logger.debug("Shell executor already running")
            return

        self._terminated = False
        self._queue = queue.Queue()

        logger.info("Starting shell executor: %s", " ".join(self._shell_command))
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

        logger.info("Shell executor started successfully (PID: %s)", self._process.pid)

    def _read_stream(self, stream: Any, stream_name: str) -> None:
        try:
            for line in stream:
                if self._terminated:
                    break
                self._queue.put((stream_name, line))
        except Exception as exc:
            logger.debug("Executor stream reader error (%s): %s", stream_name, exc)
        finally:
            logger.debug("Executor stream reader exiting: %s", stream_name)

    def send_command(self, full_command: str) -> None:
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("Shell executor is not running")
        if not self._process.stdin:
            raise RuntimeError("Shell stdin is closed")
        self._process.stdin.write(full_command)
        self._process.stdin.flush()

    def read_output(self, timeout: float = 0.1) -> tuple[str, str] | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self, timeout: float = 5.0) -> None:
        if not self._process:
            return

        self._terminated = True

        try:
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
            logger.error("Error stopping shell executor: %s", exc)
        finally:
            self._process = None
            logger.info("Shell executor stopped")

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None


class DockerExecutor(ShellExecutor):
    """Placeholder for future container-backed shell execution."""

    @property
    def executor_type(self) -> str:
        return "docker"

    def start(self) -> None:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

    def stop(self, timeout: float = 5.0) -> None:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

    def is_alive(self) -> bool:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

    def send_command(self, full_command: str) -> None:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

    def read_output(self, timeout: float = 0.1) -> tuple[str, str] | None:
        raise NotImplementedError("DockerExecutor is not yet implemented.")

