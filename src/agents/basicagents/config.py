"""
AgentConfig dataclass for unified configuration management.

Single source of truth for all agent configuration parameters.
Eliminates hardcoded values and provides type-safe configuration.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from src.core.providers.basicagents_provider_registry import BasicAgentsProviderRegistry
from src.components.basicagents.prompts.registry import PromptRegistry
from src.agents.basicagents.exceptions import (
    ConfigurationError,
    AuthenticationError,
    ProviderNotFoundError,
    ModelNotFoundError,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """
    Unified agent configuration object.

    All configuration parameters are resolved from providers.json with user overrides.
    Provides type-safe access to configuration values.

    Attributes:
        provider: Provider name (e.g., 'zhipu', 'openai')
        model: Model name (e.g., 'glm-4.5', 'gpt-4o')
        llm_params: LLM-specific parameters (temperature, max_tokens, streaming, api_key, base_url)
        agent_params: Agent runtime parameters (max_iterations, max_execution_time, agent_type)
        provider_specific: Provider-specific parameters (thinking_mode, temperature_fixed, system_prompt, extra_params)
    """

    provider: str
    model: str
    llm_params: Dict[str, Any] = field(default_factory=dict)
    agent_params: Dict[str, Any] = field(default_factory=dict)
    provider_specific: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_registry(
        cls,
        registry: BasicAgentsProviderRegistry,
        provider: str,
        model: Optional[str] = None,
        **user_params: Any
    ) -> "AgentConfig":
        """
        Create AgentConfig from registry with user parameter overrides.

        Configuration priority: user_params > config file

        Args:
            registry: Provider registry instance
            provider: Provider name
            model: Model name. If None, uses default model from config
            **user_params: User-provided parameters to override config defaults

        Returns:
            Fully resolved AgentConfig instance

        Raises:
            ProviderNotFoundError: If provider not found in registry
            ModelNotFoundError: If model not found for provider
            AuthenticationError: If API key not found in environment
            ConfigurationError: If configuration validation fails
        """
        provider = provider.lower()

        # Validate provider exists
        provider_config = registry.get_provider_config(provider)
        if not provider_config:
            available = list(registry.list_providers().keys())
            raise ProviderNotFoundError(provider, available)

        # Resolve model name
        resolved_model = model or provider_config.get("default_model")
        if not resolved_model:
            raise ConfigurationError(
                f"No default model defined for provider {provider}",
                config_key="default_model"
            )

        # Validate model exists
        model_config = registry.get_model_config(provider, resolved_model)
        if not model_config:
            available_models = list(provider_config.get("models", {}).keys())
            raise ModelNotFoundError(provider, resolved_model, available_models)

        # Merge provider and model configurations
        merged_config = cls._merge_configs(provider_config, model_config, resolved_model)

        # Apply user parameter overrides (highest priority)
        cls._apply_user_overrides(merged_config, user_params)

        # Resolve and validate API key
        api_key = cls._resolve_api_key(merged_config, provider)

        # Extract and validate configuration
        config = cls(
            provider=provider,
            model=resolved_model,
            llm_params=cls._extract_llm_params(merged_config, api_key),
            agent_params=cls._extract_agent_params(merged_config),
            provider_specific=cls._extract_provider_specific(merged_config),
        )

        # Validate configuration
        cls._validate_config(config)

        logger.info(
            f"AgentConfig created: {config.provider}/{config.model} "
            f"(temp={config.llm_params.get('temperature')}, "
            f"max_iter={config.agent_params.get('max_iterations')})"
        )

        return config

    @staticmethod
    def _merge_configs(
        provider_config: Dict[str, Any],
        model_config: Dict[str, Any],
        model_name: str
    ) -> Dict[str, Any]:
        """
        Merge provider and model configurations.

        Args:
            provider_config: Provider-level configuration
            model_config: Model-level configuration
            model_name: Resolved model name

        Returns:
            Merged configuration dictionary
        """
        merged = {
            "model": model_name,
            "api_key_env": provider_config.get("api_key_env"),
            "base_url": provider_config.get("base_url"),
            "base_url_env": provider_config.get("base_url_env"),
        }

        # Merge model configuration
        merged.update(model_config)

        # Add provider-level extra_params if exists
        if "extra_params" in provider_config:
            merged["extra_params"] = provider_config["extra_params"]

        return merged

    @staticmethod
    def _apply_user_overrides(config: Dict[str, Any], user_params: Dict[str, Any]) -> None:
        """
        Apply user parameter overrides to configuration (in-place).

        Args:
            config: Configuration dictionary to modify
            user_params: User-provided parameters
        """
        for key, value in user_params.items():
            if value is not None:
                config[key] = value

    @staticmethod
    def _resolve_base_url(config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve base_url with priority: env var > config file.

        Args:
            config: Configuration dictionary

        Returns:
            Resolved base_url or None
        """
        # First priority: environment variable override
        base_url_env = config.get("base_url_env")
        if base_url_env:
            env_value = os.getenv(base_url_env)
            if env_value:
                logger.debug(f"Using base_url from env: {base_url_env}")
                return env_value

        # Second priority: config file default
        config_base_url = config.get("base_url")
        if config_base_url:
            logger.debug(f"Using base_url from config: {config_base_url}")
            return config_base_url

        # No base_url (e.g., for Zhipu official SDK)
        return None

    @staticmethod
    def _resolve_api_key(raw_config: Dict[str, Any], provider: str) -> Optional[str]:
        """
        Resolve API key from environment variable.

        Args:
            raw_config: Raw configuration from registry
            provider: Provider name

        Returns:
            API key string or None if not required

        Raises:
            AuthenticationError: If API key is required but not found
        """
        api_key_env = raw_config.get("api_key_env")
        if not api_key_env:
            # Provider doesn't require API key (e.g., Ollama local models)
            return None

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise AuthenticationError(provider, api_key_env)

        return api_key

    @staticmethod
    def _extract_llm_params(raw_config: Dict[str, Any], api_key: Optional[str]) -> Dict[str, Any]:
        """
        Extract LLM parameters from raw configuration.

        Args:
            raw_config: Raw configuration from registry
            api_key: Resolved API key

        Returns:
            Dictionary of LLM parameters
        """
        return {
            "model": raw_config["model"],
            "temperature": raw_config.get("temperature"),
            "max_tokens": raw_config.get("max_tokens"),
            "streaming": raw_config.get("streaming", False),
            "api_key": api_key,
            "base_url": AgentConfig._resolve_base_url(raw_config),
        }

    @staticmethod
    def _extract_agent_params(raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract agent runtime parameters from raw configuration.

        Args:
            raw_config: Raw configuration from registry

        Returns:
            Dictionary of agent parameters
        """
        return {
            "agent_type": raw_config.get("agent_type", "react"),
            "max_iterations": raw_config.get("max_iterations", 8),
            "max_execution_time": raw_config.get("max_execution_time", 300),
            "memory_enabled": raw_config.get("memory_enabled", True),
        }

    @staticmethod
    def _extract_provider_specific(raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract provider-specific parameters from raw configuration.

        Uses PromptRegistry to dynamically load system prompts based on provider
        and agent_type, eliminating hardcoded file paths (follows KISS and YAGNI).

        Args:
            raw_config: Raw configuration from registry

        Returns:
            Dictionary of provider-specific parameters
        """
        provider_specific_keys = [
            "thinking_mode",
            "temperature_fixed",
            "system_prompt",
            "extra_params",
        ]

        provider_specific = {
            k: raw_config[k]
            for k in provider_specific_keys
            if k in raw_config
        }

        if not provider_specific.get("system_prompt"):
            try:
                provider = raw_config.get("provider", "").lower()
                # 关键修复：根据 agent_type 使用正确的 prompt 类型
                agent_type = raw_config.get("agent_type", "react")

                # 将 agent_type 映射到 prompt 类型
                prompt_type_map = {
                    "function_calling": "function_calling",
                    "react": "react_json",
                }
                prompt_type = prompt_type_map.get(agent_type, "react_json")

                logger.debug(
                    f"Loading system prompt: agent_type={agent_type} -> prompt_type={prompt_type}"
                )

                prompt = PromptRegistry.get_prompt(
                    agent_type=prompt_type,
                    provider=provider,
                    locale="en_US"
                )
                provider_specific["system_prompt"] = prompt
                logger.debug(
                    f"Loaded system prompt via PromptRegistry for "
                    f"provider={provider}, agent_type={agent_type}, prompt_type={prompt_type}"
                )
            except FileNotFoundError as e:
                logger.warning(
                    f"No system prompt found in PromptRegistry: {e}; "
                    "adapter will use default fallback"
                )

        return provider_specific

    @staticmethod
    def _validate_config(config: "AgentConfig") -> None:
        """
        Validate configuration parameters.

        Args:
            config: AgentConfig instance to validate

        Raises:
            ConfigurationError: If validation fails
        """
        # Validate temperature range
        temperature = config.llm_params.get("temperature")
        if temperature is not None:
            if not (0.0 <= temperature <= 2.0):
                raise ConfigurationError(
                    f"temperature must be in [0.0, 2.0], got {temperature}",
                    config_key="temperature"
                )

        # Validate max_iterations
        max_iterations = config.agent_params.get("max_iterations")
        if max_iterations is not None and max_iterations <= 0:
            raise ConfigurationError(
                f"max_iterations must be positive, got {max_iterations}",
                config_key="max_iterations"
            )

        # Validate max_execution_time
        max_execution_time = config.agent_params.get("max_execution_time")
        if max_execution_time is not None and max_execution_time <= 0:
            raise ConfigurationError(
                f"max_execution_time must be positive, got {max_execution_time}",
                config_key="max_execution_time"
            )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AgentConfig(provider={self.provider}, model={self.model}, "
            f"temperature={self.llm_params.get('temperature')}, "
            f"max_iterations={self.agent_params.get('max_iterations')})"
        )
