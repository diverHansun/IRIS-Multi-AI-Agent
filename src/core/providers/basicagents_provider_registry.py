"""
BasicAgents Provider Registry

Manages provider configurations specifically for BasicAgents.
Provides complete API configuration including base_url, api_key, and agent parameters.

Following SOLID principles:
- SRP: Only manages BasicAgents configurations
- OCP: Extendable without modifying existing code
- DIP: Depends on abstractions (config files), not concrete implementations
"""

import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BasicAgentsProviderRegistry:
    """
    Provider registry for BasicAgents module.

    Responsibilities:
    - Load and manage BasicAgents provider configurations
    - Provide complete agent configuration including API credentials
    - Resolve configuration with priority: user params > env vars > config file
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

    def get_agent_config(
        self,
        provider: str,
        model: Optional[str] = None,
        **user_params: Any
    ) -> Dict[str, Any]:
        """
        Get complete agent configuration with resolved parameters.

        Configuration priority: user_params > env vars > config file

        Args:
            provider: Provider name
            model: Model name. If None, uses default model
            **user_params: User-provided parameters to override defaults

        Returns:
            Complete agent configuration dict

        Raises:
            ValueError: If provider or model not found
        """
        provider_key = provider.lower()
        provider_config = self.get_provider_config(provider_key)

        if not provider_config:
            raise ValueError(f"Provider {provider} not found in BasicAgents registry")

        # Resolve model name
        resolved_model = model or provider_config.get("default_model")
        if not resolved_model:
            raise ValueError(f"No default model defined for provider {provider}")

        # Get model configuration
        model_config = self.get_model_config(provider_key, resolved_model)
        if not model_config:
            raise ValueError(
                f"Model {resolved_model} not found in provider {provider}"
            )

        # Build complete configuration
        config = {
            "provider": provider_key,
            "model": resolved_model,
            "api_key_env": provider_config.get("api_key_env"),
            "base_url": self._resolve_base_url(provider_config),
        }

        # Add model parameters
        config.update({
            "agent_type": model_config.get("agent_type", "react"),
            "temperature": model_config.get("temperature", 0.1),
            "max_tokens": model_config.get("max_tokens"),
            "max_iterations": model_config.get("max_iterations", 8),
            "max_execution_time": model_config.get("max_execution_time", 300),
            "memory_enabled": model_config.get("memory_enabled", True),
            "supports_tools": model_config.get("supports_tools", False),
            "streaming": model_config.get("streaming", False),
        })

        # Add optional parameters
        if "thinking_mode" in model_config:
            config["thinking_mode"] = model_config["thinking_mode"]

        if "temperature_fixed" in model_config:
            config["temperature_fixed"] = model_config["temperature_fixed"]

        if "context_window" in model_config:
            config["context_window"] = model_config["context_window"]

        # Add extra params for special providers (e.g., Ollama)
        if "extra_params" in provider_config:
            config["extra_params"] = provider_config["extra_params"]

        # Apply user overrides (highest priority)
        for key, value in user_params.items():
            if value is not None:
                config[key] = value

        logger.debug(
            f"Resolved agent config for {provider}/{resolved_model}: {config.keys()}"
        )

        return config

    def _resolve_base_url(self, provider_config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve base_url with priority: env var > config file.

        Args:
            provider_config: Provider configuration dict

        Returns:
            Resolved base_url or None
        """
        # First priority: environment variable override
        base_url_env = provider_config.get("base_url_env")
        if base_url_env:
            env_value = os.getenv(base_url_env)
            if env_value:
                logger.debug(f"Using base_url from env: {base_url_env}")
                return env_value

        # Second priority: config file default
        config_base_url = provider_config.get("base_url")
        if config_base_url:
            logger.debug(f"Using base_url from config: {config_base_url}")
            return config_base_url

        # No base_url (e.g., for Zhipu official SDK)
        return None

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for provider from environment variable.

        Args:
            provider: Provider name

        Returns:
            API key string or None if not configured
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None

        api_key_env = provider_config.get("api_key_env")
        if not api_key_env:
            return None

        return os.getenv(api_key_env)

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
