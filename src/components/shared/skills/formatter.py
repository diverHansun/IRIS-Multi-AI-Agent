"""System prompt formatter for available skills."""

from __future__ import annotations

from typing import List

from .types import SkillMetadata


class SkillPromptFormatter:
    """Format skill metadata for system prompt injection."""

    def format(self, skills: List[SkillMetadata], max_skills: int = 20) -> str:
        """Render compact skills list for system prompt context."""

        if not skills:
            return ""

        display_skills = skills[:max_skills]
        lines = ["## Available Skills", ""]
        lines.append(
            "You have access to specialized skills. "
            "To activate a skill, use read_real_file to read its SKILL.md."
        )
        lines.append("")

        for skill in display_skills:
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  Path: {skill.path}")

        if len(skills) > max_skills:
            lines.append(f"\n(showing {max_skills} of {len(skills)} skills)")

        lines.append("")
        lines.append(
            "Only read a skill's SKILL.md when the user's task "
            "matches the skill's description."
        )
        return "\n".join(lines)

