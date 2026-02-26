from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.agents.deepagents.factories.base import BaseDeepAgentFactory
from src.components.deepagents.runtime_middlewares.real_filesystem.config import build_real_filesystem_options
from src.components.deepagents.runtime_middlewares.real_filesystem import RealFilesystemMiddleware
from src.components.deepagents.runtime_middlewares.real_filesystem.security import (
    PathValidationError,
    validate_file,
)
from src.core.providers.deepagents_provider_registry import DeepAgentsProviderRegistry


class _DummyFactory(BaseDeepAgentFactory):
    function_type = "dummy"


class _DummyAdapter:
    def get_middleware_config(self) -> Dict[str, Any]:
        return {
            "filesystem": "default",
            "subagents": "default",
            "patch_tool_calls": "default",
            "shell": "default",
            "skills": "default",
        }


def test_provider_registry_includes_skills_config() -> None:
    registry = DeepAgentsProviderRegistry()
    middleware = registry.get_middleware_config()
    assert "skills" in middleware
    assert isinstance(middleware["skills"], dict)


def test_factory_resolve_middleware_config_includes_skills() -> None:
    factory = _DummyFactory()
    adapter = _DummyAdapter()

    global_cfg: Dict[str, Any] = {
        "filesystem": {"enabled": True},
        "subagents": {"enabled": True},
        "patch_tool_calls": {"enabled": True},
        "shell": {"enabled": True},
        "skills": {"enabled": True},
    }
    resolved = factory._resolve_middleware_config(adapter, global_cfg)
    assert "skills" in resolved


def test_factory_extend_filesystem_for_skills_rebuilds_tuple(tmp_path: Path) -> None:
    factory = _DummyFactory()
    middleware = RealFilesystemMiddleware(
        config={
            "enabled": True,
            "project_root": str(tmp_path),
            "security": {
                "allowed_paths": [str(tmp_path)],
                "excluded_paths": [],
                "allowed_extensions": [".md", ".py"],
            },
        }
    )

    skill_source = tmp_path / "skills"
    skill_source.mkdir(parents=True, exist_ok=True)

    factory._extend_filesystem_for_skills([skill_source], [middleware])

    security = middleware.options.security
    assert isinstance(security.allowed_paths, tuple)
    assert skill_source.resolve() in security.allowed_paths


def test_validate_file_can_ignore_excluded_for_read(tmp_path: Path) -> None:
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    target_file = blocked_dir / "data.md"
    target_file.write_text("hello", encoding="utf-8")

    options = build_real_filesystem_options(
        {
            "project_root": str(tmp_path),
            "security": {
                "allowed_paths": [str(tmp_path)],
                "excluded_paths": [str(blocked_dir)],
                "allowed_extensions": [".md"],
            },
        }
    )

    try:
        validate_file(str(target_file), options, enforce_excluded=True)
        raised = False
    except PathValidationError:
        raised = True
    assert raised is True

    path = validate_file(str(target_file), options, enforce_excluded=False)
    assert path == target_file.resolve()
