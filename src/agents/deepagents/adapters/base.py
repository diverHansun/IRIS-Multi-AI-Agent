"""Base adapter definitions for DeepAgents."""

from __future__ import annotations

from abc import ABC
from typing import Any, Dict, Iterable, Optional

from src.components.deepagents.prompts import DeepAgentPromptRegistry


class BaseDeepAgentAdapter(ABC):
    """Provide provider and model specific configuration for DeepAgents."""

    function_type: str
    PROMPT_REGISTRY = DeepAgentPromptRegistry()
    PROVIDER_ALIASES: Dict[str, str] = {
        "ANTHROPIC": "anthropic",
        "TONGYI": "openai",
        "ZHIPU": "openai",
        "OPENAI": "openai",
    }

    def __init__(self, *, provider: str, model: str, provider_config: Dict[str, Any]) -> None:
        self.provider = provider
        self.model = model
        self.provider_config = provider_config

    @property
    def base_url(self) -> Optional[str]:
        """Return provider base URL if configured."""
        return self.provider_config.get("base_url")

    @property
    def api_key_env(self) -> Optional[str]:
        """Return environment variable name for API key."""
        return self.provider_config.get("api_key_env")

    def get_model_parameters(self) -> Dict[str, Any]:
        """Return model specific configuration."""
        params = {
            key: value
            for key, value in self.provider_config.items()
            if key not in {"base_url", "api_key_env", "middleware", "description"}
        }
        allowed_keys = {
            "temperature",
            "max_tokens",
            "top_p",
            "timeout",
            "max_output_tokens",
        }
        return {
            key: value
            for key, value in params.items()
            if key in allowed_keys
        }

    def get_middleware_config(self) -> Dict[str, Any]:
        """Return middleware configuration for the agent."""
        return self.provider_config.get("middleware", {})

    def build_metadata(self) -> Dict[str, Any]:
        """Metadata describing the adapter."""
        return {
            "provider": self.provider,
            "model": self.model,
            "function_type": self.function_type,
            "description": self.provider_config.get("description"),
        }

    def get_main_agent_prompt(
        self,
        *,
        subagents: Iterable[str],
        tools: Iterable[str] | None = None,
        task_description: str | None = None,
        user_context: str | None = None,
    ) -> str:
        """Return formatted main agent system prompt."""
        return self.PROMPT_REGISTRY.get_main_agent_prompt(
            subagents=subagents,
            tools=tools,
            task_description=task_description,
            user_context=user_context,
        )

    def get_system_prompt(self, **kwargs: Any) -> Optional[str]:
        """Return system prompt for the deep agent."""
        return self.get_main_agent_prompt(
            subagents=kwargs.get("subagents", []),
            tools=kwargs.get("tools"),
            task_description=kwargs.get("task_description"),
            user_context=kwargs.get("user_context"),
        )

    def get_subagent_prompt(self, subagent_type: str, **variables: Any) -> str:
        """Return prompt template for a specific subagent type."""
        return self.PROMPT_REGISTRY.get_subagent_prompt(subagent_type, **variables)

    def get_model_identifier(self) -> str:
        """Return LangChain compatible model identifier."""
        alias = self._provider_alias(self.provider)
        return f"{alias}:{self.model}"

    def get_model_identifier_for(self, provider: str, model: str) -> str:
        """Return model identifier for subagent provider/model pair."""
        alias = self._provider_alias(provider)
        return f"{alias}:{model}"

    def _provider_alias(self, provider: str) -> str:
        alias = self.PROVIDER_ALIASES.get(provider.upper())
        if not alias:
            raise ValueError(f"Provider {provider} is not supported yet.")
        return alias

    def get_capabilities(self) -> Dict[str, Any]:
        """Return capability information exposed by the adapter."""
        return {
            "supports_tools": self.provider_config.get("supports_tools", True),
            "supports_subagents": True,
        }
