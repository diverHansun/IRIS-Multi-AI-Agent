"""Regression tests for shell session recovery after incomplete commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.components.deepagents.runtime_middlewares.shell.security import PolicyViolationError
from src.components.deepagents.runtime_middlewares.shell.session import (
    _DONE_MARKER_PREFIX,
    PersistentShellSession,
)


class _FakeExecutor:
    def __init__(self) -> None:
        self.alive = True
        self.outputs: list[tuple[str, str]] = []
        self.sent_commands: list[str] = []

    @property
    def executor_type(self) -> str:
        return "fake"

    def start(self) -> None:
        return None

    def stop(self, timeout: float = 5.0) -> None:
        self.alive = False

    def is_alive(self) -> bool:
        return self.alive

    def send_command(self, full_command: str) -> None:
        self.sent_commands.append(full_command)

    def read_output(self, timeout: float = 0.1) -> tuple[str, str] | None:
        if self.outputs:
            return self.outputs.pop(0)
        return None


def _make_session(
    tmp_path: Path,
    *,
    timeout: float = 0.05,
    max_lines: int = 10,
    policy=None,
) -> tuple[PersistentShellSession, _FakeExecutor]:
    executor = _FakeExecutor()
    session = PersistentShellSession(
        workspace=tmp_path,
        shell_command=["cmd.exe"],
        environment={},
        command_timeout=timeout,
        startup_timeout=0.1,
        max_output_lines=max_lines,
        max_output_bytes=1024,
        executor=executor,
        policy=policy,
    )
    return session, executor


def test_execute_resets_session_after_line_truncation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, executor = _make_session(tmp_path, max_lines=1)
    executor.outputs.extend([("stdout", "line1\n"), ("stdout", "line2\n")])  # triggers truncation

    stop_calls: list[float] = []

    def _fake_stop(timeout: float = 5.0) -> None:
        stop_calls.append(timeout)
        executor.alive = False

    monkeypatch.setattr(session, "stop", _fake_stop)

    result = session.execute("echo hi")

    assert result.truncated_by_lines is True
    assert result.timed_out is False
    assert stop_calls == [1.0]


def test_execute_resets_session_after_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session, executor = _make_session(tmp_path, timeout=0.01)

    stop_calls: list[float] = []

    def _fake_stop(timeout: float = 5.0) -> None:
        stop_calls.append(timeout)
        executor.alive = False

    monkeypatch.setattr(session, "stop", _fake_stop)

    result = session.execute("echo hi")

    assert result.timed_out is True
    assert stop_calls == [1.0]


def test_execute_does_not_reset_on_normal_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, executor = _make_session(tmp_path)
    executor.outputs.extend(
        [
            ("stdout", "hello\n"),
            ("stdout", f"{_DONE_MARKER_PREFIX}_fixed 0\n"),
        ]
    )

    stop_calls: list[float] = []

    def _fake_stop(timeout: float = 5.0) -> None:
        stop_calls.append(timeout)
        executor.alive = False

    monkeypatch.setattr(session, "stop", _fake_stop)
    monkeypatch.setattr(
        "src.components.deepagents.runtime_middlewares.shell.session.uuid.uuid4",
        lambda: SimpleNamespace(hex="fixed"),
    )

    result = session.execute("echo hi")

    assert result.timed_out is False
    assert result.truncated_by_lines is False
    assert result.truncated_by_bytes is False
    assert result.exit_code == 0
    assert result.blocked is False
    assert stop_calls == []


def test_execute_returns_blocked_result_when_policy_rejects(tmp_path: Path) -> None:
    class _AlwaysBlock:
        def validate(self, command: str) -> None:
            raise PolicyViolationError("blocked for test")

        def filter_environment(self, env):
            return dict(env)

    session, executor = _make_session(tmp_path, policy=_AlwaysBlock())

    result = session.execute("rm -rf /")

    assert result.blocked is True
    assert result.exit_code is None
    assert "blocked for test" in result.output
    assert executor.sent_commands == []
