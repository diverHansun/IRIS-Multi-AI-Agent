"""
Agent Adapter Base Class

Handles provider configuration lookup via ProviderRegistry and prepares agent
specific parameters for downstream factories.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.core.langchain.providers.provider_registry import (
    ProviderRegistry,
    provider_registry as default_registry,
)

logger = logging.getLogger(__name__)


class AgentAdapter(ABC):
    """Base class for agent parameter adapters."""

    def __init__(
        self,
        provider: str,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        self.provider_registry = provider_registry or default_registry
        self.provider = provider.upper()

        provider_config = self.provider_registry.get_provider_config(self.provider)
        if not provider_config:
            raise ValueError(f"Provider {self.provider} not found in registry")
        self._provider_config = provider_config

        resolved_model = model or provider_config.get("default_model")
        if not resolved_model:
            raise ValueError(f"Provider {self.provider} does not define a default model")

        model_config = self.provider_registry.get_model_config(self.provider, resolved_model)
        if model_config is None:
            logger.warning(
                "Model %s not found in provider %s configuration, using empty config",
                resolved_model,
                self.provider,
            )
            model_config = {}

        self.model = resolved_model
        self._model_config = model_config

        logger.debug("Agent adapter initialised: provider=%s model=%s", self.provider, self.model)

    def get_agent_mode_defaults(self) -> Dict[str, Any]:
        """Return agent mode defaults from provider config."""
        mode_defaults = self._provider_config.get("mode_defaults", {})
        defaults = mode_defaults.get("agent", {})
        return defaults.copy()

    def get_agent_mode_overrides(self) -> Dict[str, Any]:
        """Return agent mode overrides from model config."""
        mode_overrides = self._model_config.get("mode_overrides", {}) if self._model_config else {}
        overrides = mode_overrides.get("agent", {})
        return overrides.copy()

    def get_agent_params(self, **user_params: Any) -> Dict[str, Any]:
        """
        Merge defaults, overrides, and user supplied parameters.
        User supplied values take precedence when not None.
        """
        params = self.get_agent_mode_defaults()
        params.update(self.get_agent_mode_overrides())

        for key, value in user_params.items():
            if value is not None:
                params[key] = value

        logger.debug("Agent params for %s/%s: %s", self.provider, self.model, params)
        return params

    @abstractmethod
    def create_agent_executor(self, llm, tools, **params):
        """Create an AgentExecutor using the processed parameters."""

    def get_model_info(self) -> Dict[str, Any]:
        """Return metadata for the associated model."""
        try:
            info = self.provider_registry.get_model_info(self.provider, self.model)
        except ValueError:
            info = {
                "provider": self.provider.lower(),
                "model": self.model,
                "name": self.model,
                "description": "",
                "supports_tools": False,
                "max_tokens": None,
                "context_window": None,
                "mode_defaults": {"agent": self.get_agent_mode_defaults()},
            }
        return info

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model})"
