"""Unit tests for shell security policies."""

from __future__ import annotations

import pytest

from src.components.deepagents.runtime_middlewares.shell.security import (
    PERMISSIVE_POLICY,
    STRICT_POLICY,
    PolicyViolationError,
)


@pytest.mark.parametrize(
    "command",
    [
        "rm file.txt",
        "sudo apt install git",
        "shutdown -h now",
        "del important.txt",
        "Remove-Item temp.txt",
    ],
)
def test_strict_policy_blocks_dangerous_commands(command: str) -> None:
    with pytest.raises(PolicyViolationError):
        STRICT_POLICY.validate(command)


@pytest.mark.parametrize(
    "command",
    [
        "echo ok && echo done",
        "echo ok; echo done",
        "cat file | more",
        "echo hi > out.txt",
        "echo hi & dir",
    ],
)
def test_strict_policy_blocks_compound_and_redirection_tokens(command: str) -> None:
    with pytest.raises(PolicyViolationError):
        STRICT_POLICY.validate(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "pytest tests/unit",
        "python -V",
        "dir",
    ],
)
def test_strict_policy_allows_common_dev_commands(command: str) -> None:
    STRICT_POLICY.validate(command)


def test_permissive_policy_allows_anything() -> None:
    PERMISSIVE_POLICY.validate("rm -rf /")


def test_filter_environment_removes_sensitive_keys() -> None:
    filtered = STRICT_POLICY.filter_environment(
        {
            "PATH": "/usr/bin",
            "OPENAI_API_KEY": "secret",
            "MY_TOKEN": "token",
            "HOME": "/home/test",
        }
    )

    assert filtered == {
        "PATH": "/usr/bin",
        "HOME": "/home/test",
    }


def test_filter_environment_returns_copy_for_permissive_policy() -> None:
    env = {"PATH": "/usr/bin"}
    filtered = PERMISSIVE_POLICY.filter_environment(env)

    assert filtered == env
    assert filtered is not env

