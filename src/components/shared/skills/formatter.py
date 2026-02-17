"""System prompt formatter for available skills."""

from __future__ import annotations

from pathlib import Path
from typing import List

from .types import SkillMetadata

_MAX_RESOURCE_HINTS = 5


class SkillPromptFormatter:
    """Format skill metadata for system prompt injection."""

    def format(self, skills: List[SkillMetadata], max_skills: int = 20) -> str:
        """Render compact skills list for system prompt context."""

        if not skills:
            return ""

        display_skills = skills[:max_skills]
        has_scripts = False
        lines = ["## Available Skills", ""]
        lines.append(
            "You have access to specialized skills. "
            "To activate a skill, use read_real_file to read its SKILL.md."
        )
        lines.append("")

        for skill in display_skills:
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  Path: {skill.path}")
            skill_dir = skill.path.parent

            if skill.resources.scripts:
                has_scripts = True
                lines.append(
                    f"  Scripts: {self._format_paths(skill.resources.scripts, skill_dir)}"
                )

            if skill.resources.references:
                lines.append(
                    f"  References: {self._format_paths(skill.resources.references, skill_dir)}"
                )

        if len(skills) > max_skills:
            lines.append(f"\n(showing {max_skills} of {len(skills)} skills)")

        lines.append("")
        lines.append(
            "Only read a skill's SKILL.md when the user's task "
            "matches the skill's description."
        )
        if has_scripts:
            lines.append(
                "When Scripts are listed, run them via the shell tool "
                "(bash or powershell) using full paths."
            )
        return "\n".join(lines)

    @staticmethod
    def _format_paths(paths: List[Path], base_dir: Path) -> str:
        display = []
        for path in paths[:_MAX_RESOURCE_HINTS]:
            try:
                display.append(str(path.relative_to(base_dir)))
            except ValueError:
                display.append(str(path))
        remaining = len(paths) - len(display)
        if remaining > 0:
            display.append(f"... (+{remaining} more)")
        return ", ".join(display)
