from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class PromptRegistry:
    """
    Loads provider/locale-specific prompt templates from config/agents/basic/prompts.

    Search order (agent_type currently supports "react_json"):
    1) Provider-specific: config/agents/basic/prompts/providers/{provider}_template.md (lowercased provider)
    2) Locale default:    config/agents/basic/prompts/react_json_{locale}.md (e.g., zh_CN / en_US)
    3) Fallbacks:         zh_CN -> en_US

    Usage:
        text = PromptRegistry.get_prompt(agent_type="react_json", provider="glm", locale="zh_CN")
        rendered = PromptRegistry.render(text, tools_block="...")
    """

    BASE_DIR = Path("config/agents/basic/prompts")

    @classmethod
    def get_prompt(
        cls,
        agent_type: str = "react_json",
        provider: Optional[str] = None,
        locale: Optional[str] = "zh_CN",
    ) -> str:
        if agent_type != "react_json":
            # For now we only support react_json; raise explicit error to avoid silent misuse.
            raise ValueError(f"Unsupported agent_type: {agent_type}")

        # 1) Provider-specific
        if provider:
            provider_key = provider.strip().lower()
            provider_path = cls.BASE_DIR / "providers" / f"{provider_key}_template.md"
            if provider_path.is_file():
                return provider_path.read_text(encoding="utf-8")

        # 2) Locale default
        locale_key = (locale or "zh_CN").strip()
        locale_filename = f"react_json_{locale_key}.md"
        locale_path = cls.BASE_DIR / locale_filename
        if locale_path.is_file():
            return locale_path.read_text(encoding="utf-8")

        # 3) Fallbacks
        zh_path = cls.BASE_DIR / "react_json_zh_CN.md"
        if zh_path.is_file():
            return zh_path.read_text(encoding="utf-8")
        en_path = cls.BASE_DIR / "react_json_en_US.md"
        if en_path.is_file():
            return en_path.read_text(encoding="utf-8")

        raise FileNotFoundError("No prompt template found in config/agents/basic/prompts")

    @staticmethod
    def render(template_text: str, tools_block: str) -> str:
        """
        Inject the serialized tool schemas into the template.
        We keep it simple to avoid template engine dependencies.
        """
        # Escape braces in tools_block so PromptTemplate doesn't treat them as variables
        escaped = tools_block.replace("{", "{{").replace("}", "}}")
        return template_text.replace("{{tools_block}}", escaped)

