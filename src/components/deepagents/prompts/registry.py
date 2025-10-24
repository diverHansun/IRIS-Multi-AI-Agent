"""Prompt registry for DeepAgents."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable


class DeepAgentPromptRegistry:
    """Load and cache DeepAgent prompt templates."""

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        self.prompts_dir = Path(prompts_dir or Path(__file__).resolve().parent)

    @lru_cache(maxsize=None)
    def _load_template(self, relative_path: str) -> str:
        template_path = self.prompts_dir / relative_path
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def get_main_agent_prompt(
        self,
        *,
        subagents: Iterable[str],
        tools: Iterable[str] | None = None,
        task_description: str | None = None,
        user_context: str | None = None,
    ) -> str:
        """Return formatted main agent prompt."""
        template = self._load_template("main_agent.md")
        variables = {
            "subagents_list": self._format_bullet_list(subagents),
            "tools_list": self._format_bullet_list(tools or []),
            "task_description": task_description or "{task_description}",
            "user_context": user_context or "{user_context}",
        }
        return template.format(**variables)

    def get_subagent_prompt(
        self,
        subagent_type: str,
        **variables: Any,
    ) -> str:
        """Return prompt template for a given subagent type."""
        template = self._load_template(f"subagents/{subagent_type}.md")
        defaults: Dict[str, Any] = {
            "task_description": "{task_description}",
            "user_context": "{user_context}",
            "code_context": "{code_context}",
            "analysis_requirements": "{analysis_requirements}",
            "data_context": "{data_context}",
        }
        defaults.update(variables)
        return template.format(**defaults)

    @staticmethod
    def _format_bullet_list(items: Iterable[str]) -> str:
        entries = [item for item in items if item]
        if not entries:
            return "- None"
        return "\n".join(f"- {entry}" for entry in entries)
