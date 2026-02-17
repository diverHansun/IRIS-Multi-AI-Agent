from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.application.commands.shared.skills_commands import SkillsCommand


class _FakeRegistry:
    def __init__(self) -> None:
        self.reloaded = False

    def is_initialized(self) -> bool:
        return True

    def reload(self) -> None:
        self.reloaded = True

    def get_all_skills(self):
        return [object(), object()]

    def get_load_errors(self):
        return []


def test_usage_includes_reload_command() -> None:
    command = SkillsCommand()
    usage = command._usage()
    assert "/skills reload" in usage


def test_template_matches_anthropic_minimal_fields() -> None:
    content = SkillsCommand._skill_template("demo-skill")

    assert "name: demo-skill" in content
    assert "description:" in content
    assert "metadata:" not in content
    assert "## When to Use" not in content


def test_reload_command_executes_registry_reload(monkeypatch) -> None:
    fake_registry = _FakeRegistry()

    import src.components.shared.skills as skills_module

    monkeypatch.setattr(
        skills_module.SkillRegistry,
        "get_instance",
        classmethod(lambda cls: fake_registry),
    )

    command = SkillsCommand()
    ctx = SimpleNamespace(project_context=None)
    result = asyncio.run(command.execute(ctx, "reload"))

    assert result.type == "success"
    assert "Reloaded 2 skill(s)." in result.message
    assert fake_registry.reloaded is True

