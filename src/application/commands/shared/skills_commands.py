"""Skill management commands."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.application.commands.base import BaseCommand, CommandResult

logger = logging.getLogger(__name__)

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9]*(-[a-z0-9]+)*)?$")
MAX_SKILL_NAME_LENGTH = 64


class SkillsCommand(BaseCommand):
    """Manage agent skills: list, create, and inspect."""

    name = "skills"
    engine_scope = ("agent",)
    help_text = "Manage agent skills (list, create, info)."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.strip().split()
        if not parts:
            return CommandResult.info(self._usage())

        action = parts[0].lower()
        rest = parts[1:]

        handlers = {
            "list": self._handle_list,
            "create": self._handle_create,
            "info": self._handle_info,
        }

        handler = handlers.get(action)
        if handler is None:
            return CommandResult.error(self._usage())

        return await handler(ctx, rest)

    def _usage(self) -> str:
        return (
            "Usage:\n"
            "  /skills list\n"
            "  /skills create <name> [--project]\n"
            "  /skills info <name>"
        )

    async def _handle_list(self, ctx, args: list[str]) -> CommandResult:  # noqa: ARG002
        try:
            from src.components.shared.skills import SkillRegistry

            registry = SkillRegistry.get_instance()
            self._ensure_initialized(registry, ctx)

            skills = registry.get_all_skills()
            errors = registry.get_load_errors()

            if not skills and not errors:
                return CommandResult.info("No skills found.")

            return CommandResult.success(self._format_skill_list(skills, errors))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to list skills: %s", exc, exc_info=True)
            return CommandResult.error(f"Failed to list skills: {exc}")

    async def _handle_create(self, ctx, args: list[str]) -> CommandResult:
        if not args:
            return CommandResult.error(
                "Usage: /skills create <name> [--project]\n"
                "  Name must be lowercase alphanumeric with hyphens (e.g. web-research)"
            )

        name = args[0]
        use_project = "--project" in args

        if not self._validate_skill_name(name):
            return CommandResult.error(
                f"Name '{name}' is invalid.\n"
                "  Skill names must use lowercase letters, digits, and hyphens only.\n"
                "  Examples: web-research, code-review, my-tool-v2"
            )

        target_dir = self._resolve_target_dir(ctx, name, project=use_project)
        if target_dir is None:
            return CommandResult.error(
                "Not in a project directory. Cannot use --project flag.\n"
                "  Run this command from a directory containing .iris, .git, or pyproject.toml."
            )

        if target_dir.exists():
            return CommandResult.error(
                f"Skill '{name}' already exists at {target_dir}/\n"
                "  Use a different name or delete the existing skill first."
            )

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            skill_file = target_dir / "SKILL.md"
            skill_file.write_text(self._skill_template(name), encoding="utf-8")
            return CommandResult.success(
                f"Created skill '{name}' at:\n"
                f"  {skill_file}\n\n"
                "Edit the SKILL.md file to add your skill instructions.\n"
                "The skill will be available in your next agent session."
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to create skill '%s': %s", name, exc, exc_info=True)
            return CommandResult.error(f"Failed to create skill: {exc}")

    async def _handle_info(self, ctx, args: list[str]) -> CommandResult:
        if not args:
            return CommandResult.error("Usage: /skills info <name>")

        name = args[0]
        try:
            from src.components.shared.skills import SkillRegistry

            registry = SkillRegistry.get_instance()
            self._ensure_initialized(registry, ctx)

            skill = registry.get_skill(name)
            if skill is None:
                all_names = [item.name for item in registry.get_all_skills()]
                hint = ", ".join(all_names[:5]) if all_names else "(none)"
                return CommandResult.error(
                    f"Skill '{name}' not found.\n"
                    f"  Available skills: {hint}\n"
                    "  Run '/skills list' to see all available skills."
                )

            return CommandResult.success(self._format_skill_info(skill))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to get skill info for '%s': %s", name, exc, exc_info=True)
            return CommandResult.error(f"Failed to get skill info: {exc}")

    def _ensure_initialized(self, registry, ctx) -> None:
        if registry.is_initialized():
            return

        from src.components.shared.skills import SkillRegistry
        from src.core.providers import deepagents_provider_registry

        middleware_cfg = deepagents_provider_registry.get_middleware_config() or {}
        skills_cfg = middleware_cfg.get("skills", {}) if isinstance(middleware_cfg, dict) else {}

        project_ctx = getattr(ctx, "project_context", None)
        project_skills_dir = project_ctx.skills_dir if project_ctx else None
        sources = SkillRegistry.resolve_sources(
            config=skills_cfg if isinstance(skills_cfg, dict) else None,
            project_skills_dir=project_skills_dir,
        )
        registry.initialize(sources)

    @staticmethod
    def _validate_skill_name(name: str) -> bool:
        if not name or len(name) > MAX_SKILL_NAME_LENGTH:
            return False
        if "--" in name:
            return False
        return bool(SKILL_NAME_PATTERN.match(name))

    @staticmethod
    def _resolve_target_dir(ctx, name: str, *, project: bool) -> Optional[Path]:
        if project:
            project_ctx = getattr(ctx, "project_context", None)
            if project_ctx is None:
                return None
            return project_ctx.skills_dir / name

        from src.core.project.share import IrisShareDir

        return IrisShareDir.get_skills_dir() / name

    @staticmethod
    def _skill_template(name: str) -> str:
        return (
            "---\n"
            f"name: {name}\n"
            "description: >\n"
            "  TODO: Describe what this skill does and when to use it.\n"
            "  Include keywords that help the agent recognize relevant tasks.\n"
            "metadata:\n"
            '  author: ""\n'
            '  version: "1.0.0"\n'
            "  category: general\n"
            "---\n"
            "\n"
            f"# {name}\n"
            "\n"
            "TODO: Add skill instructions here.\n"
            "\n"
            "## When to Use\n"
            "\n"
            "Describe the scenarios where this skill should be activated.\n"
            "\n"
            "## Workflow\n"
            "\n"
            "### Step 1: ...\n"
            "\n"
            "### Step 2: ...\n"
            "\n"
            "## Edge Cases\n"
            "\n"
            "- TODO: Document edge cases\n"
        )

    @staticmethod
    def _format_skill_list(skills, errors) -> str:
        from src.components.shared.skills import SkillSourceType

        grouped: Dict[str, List] = {
            "Built-in": [],
            "User": [],
            "Project": [],
        }
        source_labels = {
            SkillSourceType.BUILT_IN: "Built-in",
            SkillSourceType.USER: "User",
            SkillSourceType.PROJECT: "Project",
        }

        for skill in skills:
            label = source_labels.get(skill.source_type, "Unknown")
            grouped[label].append(skill)

        lines = ["Skills:"]
        total = 0
        for label, group in grouped.items():
            if not group:
                continue
            lines.append(f"\n  {label}:")
            for skill in group:
                desc = (skill.description or "")[:60]
                lines.append(f"    {skill.name:<24} {desc}")
                total += 1

        if errors:
            lines.append("\n  Warnings:")
            for err in errors:
                lines.append(f"    [WARN] {err.path}: {err.message}")

        lines.append(f"\n  Total: {total} skill(s)")
        return "\n".join(lines)

    @staticmethod
    def _format_skill_info(skill) -> str:
        lines = [
            f"Skill: {skill.name}",
            f"Source: {skill.source_type.value} ({skill.path.parent})",
            f"Description: {skill.description or '(none)'}",
        ]

        if skill.metadata:
            lines.append("\nMetadata:")
            for key, value in skill.metadata.items():
                lines.append(f"  {key}: {value}")

        if skill.allowed_tools:
            lines.append(f"\nAllowed Tools: {', '.join(skill.allowed_tools)}")

        if skill.user_invocable is not None:
            lines.append(f"User Invocable: {skill.user_invocable}")

        return "\n".join(lines)


__all__ = ["SkillsCommand"]

