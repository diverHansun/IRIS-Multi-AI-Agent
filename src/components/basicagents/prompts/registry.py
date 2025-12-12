from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class PromptRegistry:
    """
    Loads provider/locale-specific prompt templates from src/components/basicagents/prompts.

    Search order (agent_type supports "react_json" and "function_calling"):
    1) Provider-specific:   src/components/basicagents/prompts/providers/{provider}_template.md
    2) Agent-type default:  src/components/basicagents/prompts/{agent_type}/{agent_type}_{locale}.md
    3) Locale fallback:     {agent_type}_{alternate_locale}.md (e.g., zh_CN -> en_US)
    4) Legacy (react only): src/components/basicagents/prompts/ReAct/react_json_{locale}.md

    Usage:
        text = PromptRegistry.get_prompt(agent_type="react_json", provider="glm", locale="zh_CN")
        text = PromptRegistry.get_prompt(agent_type="function_calling", provider="zhipu", locale="zh_CN")
        rendered = PromptRegistry.render(text, tools_block="...")
    """

    BASE_DIR = Path(__file__).resolve().parent

    @classmethod
    def get_prompt(
        cls,
        agent_type: str = "react_json",
        provider: Optional[str] = None,
        locale: Optional[str] = "zh_CN",
    ) -> str:
        # Validate agent_type
        supported_types = {"react_json", "function_calling"}
        if agent_type not in supported_types:
            raise ValueError(
                f"Unsupported agent_type: {agent_type}. "
                f"Supported types: {supported_types}"
            )

        # 1) Provider-specific (highest priority)
        if provider:
            provider_key = provider.strip().lower()
            provider_path = cls.BASE_DIR / "providers" / f"{provider_key}_template.md"
            if provider_path.is_file():
                return provider_path.read_text(encoding="utf-8")

        # 2) Agent-type specific directory
        locale_key = (locale or "en_US").strip()

        # Try exact locale match first (e.g., en_US, zh_CN)
        locale_filename = f"{agent_type}_{locale_key}.md"
        agent_type_path = cls.BASE_DIR / agent_type / locale_filename
        if agent_type_path.is_file():
            return agent_type_path.read_text(encoding="utf-8")

        # Try simplified locale (e.g., en_US -> en, zh_CN -> zh)
        locale_short = locale_key.split("_")[0]
        short_filename = f"{agent_type}_{locale_short}.md"
        short_path = cls.BASE_DIR / agent_type / short_filename
        if short_path.is_file():
            return short_path.read_text(encoding="utf-8")

        # 3) Fallback: try alternate locale (zh_CN -> en, en_US -> en, etc.)
        if locale_key != "en_US" and locale_short != "en":
            fallback_filename = f"{agent_type}_en.md"
            fallback_path = cls.BASE_DIR / agent_type / fallback_filename
            if fallback_path.is_file():
                return fallback_path.read_text(encoding="utf-8")

        # 4) Legacy fallback for react_json in ReAct directory (backward compatibility)
        if agent_type == "react_json":
            en_path = cls.BASE_DIR / "ReAct" / "react_json_en.md"
            if en_path.is_file():
                return en_path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"No prompt template found for agent_type={agent_type}, "
            f"provider={provider}, locale={locale_key} in "
            f"src/components/basicagents/prompts"
        )

    @staticmethod
    def render(template_text: str, tools_block: str) -> str:
        """
        Inject the serialized tool schemas into the template.
        We keep it simple to avoid template engine dependencies.
        """
        # Escape braces in tools_block so PromptTemplate doesn't treat them as variables
        escaped = tools_block.replace("{", "{{").replace("}", "}}")
        return template_text.replace("{{tools_block}}", escaped)

