"""
Provider Registry

Provider registration table, responsible for loading and managing all Providers from config files.
This is a shared module used by both LLM and Agent modules.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

from src.config import config_loader

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM provider enumeration"""
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"


class ProviderRegistry:
    """
    Provider Registry

    Responsibilities:
    - Load Provider configurations from config files
    - Provide Provider query interface
    - Validate models
    """

    def __init__(self):
        """Initialize Provider registry"""
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._load_from_config()

    def _load_from_config(self):
        """Load Provider configurations from config file"""
        try:
            config_data = config_loader.load_config()
            self._providers = config_data.get("providers", {})

            logger.info(f"Loaded {len(self._providers)} Provider configurations")

        except Exception as e:
            logger.error(f"Failed to load Provider configurations: {e}")
            self._providers = {}

    def reload_config(self):
        """Reload configuration"""
        logger.info("Reloading Provider configurations...")
        try:
            config_data = config_loader.reload_config()
            self._providers = config_data.get("providers", {})
            logger.info("Provider configurations reloaded")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configurations: {e}")
            return False

    def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get Provider configuration

        Args:
            provider: Provider name

        Returns:
            Provider configuration, None if not exists
        """
        provider_key = provider.upper()
        return self._providers.get(provider_key)

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        List all Provider configurations

        Returns:
            All Provider configurations
        """
        return self._providers.copy()

    def get_model_config(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get model configuration

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Model configuration, None if not exists
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None

        models = provider_config.get("models", {})
        return models.get(model)

    def get_model_info(self, provider: str, model: str = None) -> Dict[str, Any]:
        """
        Get detailed model information (including merged mode_defaults and mode_overrides)

        Args:
            provider: Provider name
            model: Model name, uses default model if None

        Returns:
            Model information

        Raises:
            ValueError: If provider or model not found
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")

        if model is None:
            model = provider_config.get("default_model")

        model_config = self.get_model_config(provider, model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")

        mode_defaults = provider_config.get("mode_defaults", {})
        mode_overrides = model_config.get("mode_overrides", {})

        llm_defaults = mode_defaults.get("llm", {})
        llm_overrides = mode_overrides.get("llm", {})
        llm_params = {**llm_defaults, **llm_overrides}

        agent_defaults = mode_defaults.get("agent", {})
        agent_overrides = mode_overrides.get("agent", {})
        agent_params = {**agent_defaults, **agent_overrides}

        return {
            "provider": provider.lower(),
            "provider_name": provider_config.get("name"),
            "model": model,
            "model_name": model_config.get("name", model),
            "name": model_config.get("name", model),
            "description": model_config.get("description", ""),
            "recommended": model_config.get("recommended", False),
            "model_features": model_config.get("model_features", []),
            "supports_tools": model_config.get("supports_tools", False),
            "max_tokens": model_config.get("max_tokens"),
            "context_window": model_config.get("context_window"),
            "mode_defaults": {
                "llm": llm_params,
                "agent": agent_params
            }
        }

    def validate_model(self, provider: str, model: str) -> bool:
        """
        Validate if model is supported

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Whether the model is supported
        """
        model_config = self.get_model_config(provider, model)
        return model_config is not None

    def __repr__(self) -> str:
        return f"ProviderRegistry(providers={list(self._providers.keys())})"


# Global module-level Provider registry instance
provider_registry = ProviderRegistry()
