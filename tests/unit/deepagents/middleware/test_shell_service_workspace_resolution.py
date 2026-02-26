"""Unit tests for shell workspace resolution in the service layer."""

from pathlib import Path

from src.application.services.agent.deep.middleware.shell_service import (
    ShellMiddlewareService,
)


def test_resolve_workspace_auto_uses_project_root(tmp_path: Path) -> None:
    raw = {"enabled": True, "workspace_root": "auto"}

    resolved = ShellMiddlewareService.resolve_workspace(raw, project_root=tmp_path)

    assert resolved["workspace_root"] == str(tmp_path.resolve())
    assert raw["workspace_root"] == "auto"


def test_resolve_workspace_dot_uses_project_root(tmp_path: Path) -> None:
    resolved = ShellMiddlewareService.resolve_workspace(
        {"workspace_root": "."},
        project_root=tmp_path,
    )

    assert resolved["workspace_root"] == str(tmp_path.resolve())


def test_resolve_workspace_relative_path_uses_project_root(tmp_path: Path) -> None:
    resolved = ShellMiddlewareService.resolve_workspace(
        {"workspace_root": "sandbox/output"},
        project_root=tmp_path,
    )

    assert resolved["workspace_root"] == str((tmp_path / "sandbox" / "output").resolve())


def test_resolve_workspace_absolute_path_is_unchanged(tmp_path: Path) -> None:
    absolute = (tmp_path / "custom").resolve()
    resolved = ShellMiddlewareService.resolve_workspace(
        {"workspace_root": str(absolute)},
        project_root=tmp_path,
    )

    assert resolved["workspace_root"] == str(absolute)


def test_resolve_workspace_without_project_root_returns_copy() -> None:
    raw = {"workspace_root": "auto", "enabled": True}

    resolved = ShellMiddlewareService.resolve_workspace(raw, project_root=None)

    assert resolved == raw
    assert resolved is not raw
