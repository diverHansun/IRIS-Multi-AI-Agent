from __future__ import annotations

from pathlib import Path

import pytest

from src.components.shared.skills import (
    SkillLoader,
    SkillMetadata,
    SkillPromptFormatter,
    SkillRegistry,
    SkillResources,
    SkillSource,
    SkillSourceType,
    SkillValidator,
)
from src.core.project.share import IrisShareDir


def _write_skill(skill_dir: Path, *, name: str, description: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        f"name: {name}\n"
        "description: >\n"
        f"  {description}\n"
        "metadata:\n"
        '  author: "tests"\n'
        "---\n\n"
        f"# {name}\n",
        encoding="utf-8",
    )


def test_loader_parses_skills_and_reports_errors(tmp_path: Path) -> None:
    source_dir = tmp_path / "skills"
    _write_skill(source_dir / "valid-skill", name="valid-skill", description="A valid skill")

    broken_dir = source_dir / "broken-skill"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "SKILL.md").write_text("---\nname: [invalid\n---\n", encoding="utf-8")

    source = SkillSource(type=SkillSourceType.USER, path=source_dir, priority=1)
    loader = SkillLoader()
    skills = loader.load_from_source(source)
    errors = loader.get_last_errors()

    assert len(skills) == 1
    assert skills[0].name == "valid-skill"
    assert skills[0].source_type == SkillSourceType.USER
    assert errors
    assert "invalid YAML frontmatter" in errors[0].message

    validator = SkillValidator()
    ok, validation_errors = validator.validate_basic(skills[0])
    assert ok
    assert validation_errors == []


def test_registry_precedence_user_overrides_builtin(tmp_path: Path) -> None:
    built_in = tmp_path / "built-in"
    user = tmp_path / "user"

    _write_skill(
        built_in / "overlap-skill",
        name="overlap-skill",
        description="built-in description",
    )
    _write_skill(
        user / "overlap-skill",
        name="overlap-skill",
        description="user description",
    )

    registry = SkillRegistry()
    registry.initialize(
        [
            SkillSource(type=SkillSourceType.BUILT_IN, path=built_in, priority=0),
            SkillSource(type=SkillSourceType.USER, path=user, priority=1),
        ]
    )

    skill = registry.get_skill("overlap-skill")
    assert skill is not None
    assert skill.description == "user description"
    assert skill.source_type == SkillSourceType.USER


def test_prompt_formatter_respects_max_skills() -> None:
    formatter = SkillPromptFormatter()
    skills = [
        SkillMetadata(name=f"skill-{idx}", description=f"description {idx}")
        for idx in range(3)
    ]

    prompt = formatter.format(skills, max_skills=2)

    assert "skill-0" in prompt
    assert "skill-1" in prompt
    assert "skill-2" not in prompt
    assert "(showing 2 of 3 skills)" in prompt


def test_registry_resolve_sources_uses_shared_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built_in_dir = tmp_path / "built-in"
    user_dir = tmp_path / "user"
    project_dir = tmp_path / "project"
    built_in_dir.mkdir()
    user_dir.mkdir()
    project_dir.mkdir()

    import src.components.shared.skills.registry as registry_module

    monkeypatch.setattr(registry_module, "BUILT_IN_SKILLS_DIR", built_in_dir)
    monkeypatch.setattr(
        IrisShareDir,
        "get_skills_dir",
        classmethod(lambda cls: user_dir),
    )

    sources = SkillRegistry.resolve_sources(
        config={"sources": {"built_in": True, "user": True, "project": False}},
        project_skills_dir=project_dir,
    )

    assert [source.type for source in sources] == [SkillSourceType.BUILT_IN, SkillSourceType.USER]
    assert all(source.path.exists() for source in sources)


def test_loader_rejects_unexpected_frontmatter_fields(tmp_path: Path) -> None:
    source_dir = tmp_path / "skills"
    skill_dir = source_dir / "bad-field"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: bad-field\n"
        "description: bad field test\n"
        "user-invocable: true\n"
        "---\n\n"
        "# bad-field\n",
        encoding="utf-8",
    )

    source = SkillSource(type=SkillSourceType.USER, path=source_dir, priority=1)
    loader = SkillLoader()
    skills = loader.load_from_source(source)
    errors = loader.get_last_errors()

    assert skills == []
    assert len(errors) == 1
    assert "unexpected frontmatter field(s)" in errors[0].message


def test_loader_scans_scripts_and_reference_alias(tmp_path: Path) -> None:
    source_dir = tmp_path / "skills"
    skill_dir = source_dir / "resource-skill"
    _write_skill(skill_dir, name="resource-skill", description="Resource skill")

    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "run.py").write_text("print('ok')\n", encoding="utf-8")

    reference_dir = skill_dir / "reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    (reference_dir / "guide.md").write_text("# guide\n", encoding="utf-8")

    source = SkillSource(type=SkillSourceType.USER, path=source_dir, priority=1)
    loader = SkillLoader()
    skills = loader.load_from_source(source)

    assert len(skills) == 1
    skill = skills[0]
    assert [item.name for item in skill.resources.scripts] == ["run.py"]
    assert [item.name for item in skill.resources.references] == ["guide.md"]


def test_prompt_formatter_includes_script_hints() -> None:
    formatter = SkillPromptFormatter()
    skill = SkillMetadata(
        name="script-skill",
        description="Uses scripts",
        path=Path("/tmp/script-skill/SKILL.md"),
        resources=SkillResources(
            scripts=[Path("/tmp/script-skill/scripts/run.py")],
            references=[Path("/tmp/script-skill/references/guide.md")],
        ),
    )

    prompt = formatter.format([skill], max_skills=5)

    assert "Scripts:" in prompt and "run.py" in prompt
    assert "References:" in prompt and "guide.md" in prompt
    assert "run them via the shell tool" in prompt
