"""
BasicAgents Provider Registry

Pure data layer for BasicAgents configurations.
Loads and caches configuration data from providers.json without business logic.

Following SOLID principles:
- SRP: Only manages raw configuration data loading and retrieval
- OCP: Extendable without modifying existing code
- DIP: Depends on abstractions (config files), not concrete implementations

Design:
- Data layer: BasicAgentsProviderRegistry (this file) - read/cache config
- Logic layer: AgentConfig (agents/basicagents/config.py) - parse/validate/transform
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BasicAgentsProviderRegistry:
    """
    Provider registry for BasicAgents module (Data Layer).

    Responsibilities:
    - Load provider configurations from JSON file
    - Cache and provide raw configuration data
    - Reload configuration on demand

    NOT responsible for:
    - Merging configurations (handled by AgentConfig)
    - Resolving API keys (handled by AgentConfig)
    - Parameter validation (handled by AgentConfig)
    - Business logic (handled by AgentConfig)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize BasicAgents provider registry.

        Args:
            config_path: Path to configuration file. If None, uses default path.
        """
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._config_path = config_path or "config/agents/basic/models/providers.json"
        self._load_from_config()

    def _load_from_config(self) -> None:
        """Load provider configurations from JSON file."""
        try:
            import json

            with open(self._config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            self._providers = config_data.get("providers", {})
            logger.info(f"Loaded {len(self._providers)} BasicAgents provider configurations")

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self._config_path}")
            self._providers = {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            self._providers = {}
        except Exception as e:
            logger.error(f"Failed to load provider configurations: {e}")
            self._providers = {}

    def reload_config(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            True if reload successful, False otherwise
        """
        logger.info("Reloading BasicAgents provider configurations...")
        try:
            self._load_from_config()
            return True
        except Exception as e:
            logger.error(f"Failed to reload configurations: {e}")
            return False

    def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get provider configuration.

        Args:
            provider: Provider name (case-insensitive)

        Returns:
            Provider configuration dict or None if not found
        """
        provider_key = provider.lower()
        return self._providers.get(provider_key)

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        List all provider configurations.

        Returns:
            Dictionary of all provider configurations
        """
        return self._providers.copy()

    def get_model_config(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get model configuration for a specific provider.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            Model configuration dict or None if not found
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None

        models = provider_config.get("models", {})
        return models.get(model)

    def get_default_model(self, provider: str) -> Optional[str]:
        """
        Get default model name for provider.

        Args:
            provider: Provider name

        Returns:
            Default model name or None if not configured
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None
        return provider_config.get("default_model")

    def list_models(self, provider: str) -> Dict[str, Dict[str, Any]]:
        """
        List all models for a provider.

        Args:
            provider: Provider name

        Returns:
            Dictionary of model configurations
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return {}
        return provider_config.get("models", {})

    def validate_model(self, provider: str, model: str) -> bool:
        """
        Validate if model is supported by provider.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            True if model is supported, False otherwise
        """
        model_config = self.get_model_config(provider, model)
        return model_config is not None

    def __repr__(self) -> str:
        return f"BasicAgentsProviderRegistry(providers={list(self._providers.keys())})"


# Global BasicAgents registry instance
basicagents_registry = BasicAgentsProviderRegistry()
