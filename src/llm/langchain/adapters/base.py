"""
LLM Adapter Base Class

Provides a shared abstraction for provider specific LLM adapters.
Configuration access is delegated to ProviderRegistry to avoid repeated file I/O.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.core.langchain.providers.provider_registry import (
    ProviderRegistry,
    provider_registry as default_registry,
)

logger = logging.getLogger(__name__)


class LLMAdapter(ABC):
    """
    LLM adapter abstract base class.

    Responsibilities:
    - Merge provider defaults and model overrides for LLM parameters.
    - Allow subclasses to apply provider specific adjustments.
    - Keep parameter management focused on LLM concerns only.
    """

    def __init__(
        self,
        provider: str,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
        mode: str = "llm",
    ):
        self.provider_registry = provider_registry or default_registry
        self.provider = provider.upper()
        self.mode = mode

        provider_config = self.provider_registry.get_provider_config(self.provider)
        if not provider_config:
            raise ValueError(f"Provider {self.provider} not found in registry")
        self._provider_config = provider_config

        resolved_model = model or provider_config.get("default_model")
        if not resolved_model:
            raise ValueError(f"Provider {self.provider} does not define a default model")

        model_config = self.provider_registry.get_model_config(self.provider, resolved_model)
        if model_config is None:
            if self._provider_config.get("models"):
                logger.warning(
                    "Model %s not found in provider %s configuration, using empty config",
                    resolved_model,
                    self.provider,
                )
            model_config = {}

        self.model = resolved_model
        self._model_config = model_config

        logger.debug(
            "LLM adapter initialized: provider=%s model=%s mode=%s",
            self.provider,
            self.model,
            self.mode,
        )

    def get_llm_mode_defaults(self) -> Dict[str, Any]:
        """Return llm mode defaults from provider config."""
        mode_defaults = self._provider_config.get("mode_defaults", {})
        llm_defaults = mode_defaults.get("llm", {})
        return llm_defaults.copy()

    def get_llm_mode_overrides(self) -> Dict[str, Any]:
        """Return llm mode overrides from model config."""
        mode_overrides = self._model_config.get("mode_overrides", {}) if self._model_config else {}
        llm_overrides = mode_overrides.get("llm", {})
        return llm_overrides.copy()

    def get_base_params(self) -> Dict[str, Any]:
        """Merge defaults and overrides to form the base parameter set."""
        params = self.get_llm_mode_defaults()
        params.update(self.get_llm_mode_overrides())
        return params

    @abstractmethod
    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        Return processed LLM parameters.
        Subclasses should only manipulate parameters relevant to LLM behaviour.
        """

    def merge_user_params(self, base_params: Dict[str, Any], user_params: Dict[str, Any]) -> Dict[str, Any]:
        """Merge user supplied parameters into the base parameter set, ignoring None values."""
        merged = base_params.copy()
        for key, value in user_params.items():
            if value is not None:
                merged[key] = value
        return merged

    def get_model_info(self) -> Dict[str, Any]:
        """Expose model metadata."""
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
                "mode_defaults": {"llm": self.get_llm_mode_defaults()},
            }
        info["mode"] = self.mode
        return info

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model}, mode={self.mode})"
