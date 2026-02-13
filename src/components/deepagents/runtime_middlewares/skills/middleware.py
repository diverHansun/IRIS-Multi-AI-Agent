"""Skills middleware for deep agent runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.runtime import Runtime

from src.components.shared.skills import SkillPromptFormatter, SkillRegistry, SkillSource


class SkillsMiddleware(AgentMiddleware):
    """Inject available skill metadata into the system prompt."""

    def __init__(
        self,
        *,
        config: Dict[str, Any] | None = None,
        sources: List[SkillSource] | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        super().__init__()
        self._config = self._load_config(config)
        self._sources = sources or []
        self._registry = registry
        self._formatter = SkillPromptFormatter()

    def before_agent(self, state, runtime: Runtime[Any]) -> Dict[str, Any] | None:  # noqa: ARG002
        if self._registry is None:
            self._registry = SkillRegistry.get_instance()
            if not self._registry.is_initialized() and self._sources:
                self._registry.initialize(self._sources)
            elif not self._registry.is_initialized():
                # Fallback for direct middleware usage outside factory.
                fallback_sources = SkillRegistry.resolve_sources(config=self._config)
                self._registry.initialize(fallback_sources)
        return None

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        if self._registry and self._config.get("enabled", True):
            skills = self._registry.get_all_skills()
            if skills:
                prompt_cfg = self._config.get("prompt", {}) if isinstance(self._config, dict) else {}
                max_skills = int(prompt_cfg.get("max_skills_in_prompt", 20))
                skill_prompt = self._formatter.format(skills, max_skills=max_skills)
                if request.system_prompt:
                    request.system_prompt = f"{request.system_prompt}\n\n{skill_prompt}"
                else:
                    request.system_prompt = skill_prompt
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler):
        if self._registry and self._config.get("enabled", True):
            skills = self._registry.get_all_skills()
            if skills:
                prompt_cfg = self._config.get("prompt", {}) if isinstance(self._config, dict) else {}
                max_skills = int(prompt_cfg.get("max_skills_in_prompt", 20))
                skill_prompt = self._formatter.format(skills, max_skills=max_skills)
                if request.system_prompt:
                    request.system_prompt = f"{request.system_prompt}\n\n{skill_prompt}"
                else:
                    request.system_prompt = skill_prompt
        return await handler(request)

    @staticmethod
    def _load_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        base_config: Dict[str, Any] = {
            "enabled": True,
            "sources": {
                "built_in": True,
                "user": True,
                "project": True,
            },
            "prompt": {
                "format": "simple",
                "max_skills_in_prompt": 20,
            },
            "validation": {
                "strict_name_check": True,
                "warn_on_missing_description": True,
            },
        }
        if not config:
            return base_config

        merged = dict(base_config)
        for key, value in config.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                section = dict(merged[key])
                section.update(value)
                merged[key] = section
            else:
                merged[key] = value
        return merged

    def describe(self) -> Dict[str, Any]:
        """Return middleware summary for diagnostics."""

        return {
            "enabled": bool(self._config.get("enabled", True)),
            "sources_count": len(self._sources),
            "prompt_format": self._config.get("prompt", {}).get("format", "simple"),
            "max_skills_in_prompt": self._config.get("prompt", {}).get("max_skills_in_prompt", 20),
        }

