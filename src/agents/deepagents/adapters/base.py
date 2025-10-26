"""Base adapter definitions for DeepAgents."""

from __future__ import annotations

from abc import ABC
from typing import Any, Dict, Iterable, Optional

from src.components.deepagents.prompts import DeepAgentPromptRegistry


class BaseDeepAgentAdapter(ABC):
    """
    Provide provider and model specific configuration for DeepAgents.

    This adapter now works with the new categorized configuration structure
    from DeepAgentsProviderRegistry.
    """

    function_type: str
    PROMPT_REGISTRY = DeepAgentPromptRegistry()
    PROVIDER_ALIASES: Dict[str, str] = {
        "anthropic": "openai",
        "tongyi": "openai",
        "zhipu": "openai",
        "openai": "openai",
    }

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        provider_registry: Optional[Any] = None,
    ) -> None:
        """
        Initialize adapter with provider and model.

        Args:
            provider: Provider name
            model: Model name
            provider_registry: Optional registry instance. If None, uses global registry.
        """
        self.provider = provider
        self.model = model

        # Get registry if not provided
        if provider_registry is None:
            from src.core.providers import deepagents_provider_registry

            provider_registry = deepagents_provider_registry

        self.provider_registry = provider_registry

        # Load categorized configuration
        self._complete_config = provider_registry.get_complete_config(provider, model)

    @property
    def base_url(self) -> Optional[str]:
        """Return provider base URL if configured."""
        return self._complete_config["api_config"].get("base_url")

    @property
    def api_key_env(self) -> Optional[str]:
        """Return environment variable name for API key."""
        return self._complete_config["api_config"].get("api_key_env")

    def get_llm_params(self) -> Dict[str, Any]:
        """
        Get clean LLM parameters for init_chat_model.

        Returns only parameters that are valid for the LLM API.
        """
        return self.provider_registry.get_llm_params(self.provider, self.model)

    def get_runtime_config(self) -> Dict[str, Any]:
        """Get runtime configuration for agent graph."""
        return self._complete_config["runtime_config"]

    def get_middleware_config(self) -> Dict[str, Any]:
        """Return middleware configuration for the agent."""
        return self._complete_config["middleware_config"]

    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration for streaming and logging."""
        return self._complete_config["display_config"]

    def get_safety_config(self) -> Dict[str, Any]:
        """Get safety configuration including HITL settings."""
        return self._complete_config["safety_config"]

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata (informational only)."""
        return self._complete_config["metadata"]

    def build_metadata(self) -> Dict[str, Any]:
        """Metadata describing the adapter."""
        return {
            "provider": self.provider,
            "model": self.model,
            "function_type": self.function_type,
            "description": self._complete_config.get("description"),
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
        alias = self.PROVIDER_ALIASES.get(provider.lower())
        if not alias:
            raise ValueError(f"Provider {provider} is not supported yet.")
        return alias

    def get_capabilities(self) -> Dict[str, Any]:
        """Return capability information exposed by the adapter."""
        metadata = self.get_metadata()
        return {
            "supports_tools": metadata.get("supports_tools", True),
            "supports_subagents": True,
        }
