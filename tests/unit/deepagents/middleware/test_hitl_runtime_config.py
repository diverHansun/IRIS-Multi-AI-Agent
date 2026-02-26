"""Unit tests for runtime HITL configuration adjustments."""

from __future__ import annotations

from src.application.services.agent.deep.streaming.conversation import (
    _build_effective_hitl_config,
    _resolve_shell_workspace_for_preview,
)


def _base_hitl_config() -> dict:
    return {
        "dangerous_tools": ["shell", "write_real_file"],
        "tools": {
            "shell": {
                "allow_auto_approve": False,
                "warning_message": "Shell commands can change host data.",
            },
            "write_real_file": {"allow_auto_approve": False},
        },
    }


def test_effective_hitl_config_keeps_shell_dangerous_when_security_policy_disabled() -> None:
    metadata = {
        "middleware": {
            "shell": {
                "enabled": True,
                "workspace_root": "/project",
                "security_policy": {"enabled": False},
            }
        }
    }

    effective = _build_effective_hitl_config(metadata, _base_hitl_config())

    assert "shell" in effective["dangerous_tools"]
    assert effective["tools"]["shell"]["allow_auto_approve"] is False


def test_effective_hitl_config_relaxes_shell_when_security_policy_enabled() -> None:
    metadata = {
        "middleware": {
            "shell": {
                "enabled": True,
                "workspace_root": "/project",
                "security_policy": {"enabled": True},
            }
        }
    }

    effective = _build_effective_hitl_config(metadata, _base_hitl_config())

    assert "shell" not in effective["dangerous_tools"]
    assert effective["tools"]["shell"]["allow_auto_approve"] is True
    # Other tools remain untouched
    assert "write_real_file" in effective["dangerous_tools"]
    assert effective["tools"]["write_real_file"]["allow_auto_approve"] is False


def test_resolve_shell_workspace_for_preview_ignores_auto_value() -> None:
    metadata = {
        "middleware": {
            "shell": {
                "workspace_root": "auto",
            }
        }
    }

    assert _resolve_shell_workspace_for_preview(metadata) is None


def test_resolve_shell_workspace_for_preview_prefers_resolved_workspace() -> None:
    metadata = {
        "middleware": {
            "shell": {
                "workspace_root": "auto",
                "resolved_workspace_root": "D:/work/project",
            }
        }
    }

    assert _resolve_shell_workspace_for_preview(metadata) == "D:/work/project"
