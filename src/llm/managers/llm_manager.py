"""
LLM Manager

Centralised entry point for creating LangChain compatible LLM clients.
Delegates configuration to ProviderRegistry and parameter handling to adapters.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from src.config import settings
from src.core.providers import provider_registry
from src.llm.adapters import (
    ZhipuAdapter,
    OpenAIAdapter,
    OllamaAdapter,
)
from src.llm.instances import (
    ZhipuAILLM,
    OpenAILLM,
    OllamaLLM,
)

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""

    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"


class LLMManager:
    """
    Central coordinator for LLM creation.

    Responsibilities:
    - Manage provider configuration via ProviderRegistry.
    - Collect API credentials from settings and user overrides.
    - Use adapters to normalise LLM parameters.
    - Instantiate provider specific LLM wrappers.
    """

    def __init__(self):
        self.provider_registry = provider_registry
        self._api_keys: Dict[LLMProvider, str] = {}
        self._adapter_map = {
            "ZHIPU": ZhipuAdapter,
            "OPENAI": OpenAIAdapter,
            "OLLAMA": OllamaAdapter,
        }
        self._instance_map = {
            "ZHIPU": ZhipuAILLM,
            "OPENAI": OpenAILLM,
            "OLLAMA": OllamaLLM,
        }
        self._load_api_keys()
        logger.info("LLM Manager initialised")

    def _load_api_keys(self) -> None:
        """Load API keys from settings."""
        try:
            if settings.zhipu_api_key:
                self._api_keys[LLMProvider.ZHIPU] = settings.zhipu_api_key
            if settings.openai_api_key:
                self._api_keys[LLMProvider.OPENAI] = settings.openai_api_key
        except Exception as exc:
            logger.warning("Failed to load API keys from settings: %s", exc)

    def reload_config(self) -> bool:
        """Reload provider configuration."""
        logger.info("Reloading LLM configuration")
        return self.provider_registry.reload_config()

    async def create_llm(
        self,
        provider: Union[str, LLMProvider],
        model: Optional[str] = None,
        mode: str = "llm",
        **kwargs,
    ):
        """
        Create an LLM instance.

        Args:
            provider: Provider identifier.
            model: Model name, uses provider default when omitted.
            mode: Behavioural mode for adapter, defaults to "llm".
            **kwargs: User supplied overrides.

        Returns:
            LangChain compatible LLM client.
        """
        provider_key, provider_enum = self._normalise_provider(provider)
        provider_config = self._get_provider_config(provider_key)
        model_name = self._resolve_model_name(provider_config, model)

        user_params = kwargs.copy()
        explicit_api_key = user_params.pop("api_key", None)

        adapter = self._create_adapter(provider_key, model_name, mode)

        # Resolve auto model for Ollama provider
        if provider_key == "OLLAMA" and model_name == "auto":
            base_url = (
                user_params.get("base_url")
                or kwargs.get("base_url")
                or settings.ollama_base_url
            )
            model_name = await adapter.resolve_auto_model(base_url)
            logger.info("Resolved Ollama 'auto' to actual model: %s", model_name)

        llm_params = adapter.get_llm_params(**user_params)
        llm_params["model"] = model_name  # Ensure resolved model is used

        final_params = self._prepare_instance_params(
            provider_key=provider_key,
            provider_enum=provider_enum,
            adapter=adapter,
            adapter_params=llm_params,
            explicit_api_key=explicit_api_key,
            user_params=user_params,
        )

        instance = self._create_instance(provider_key, final_params)
        llm = instance.create_llm()
        logger.info("Created LLM instance: provider=%s model=%s", provider_key, model_name)
        return llm

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Return available provider summary with model information."""
        providers: List[Dict[str, Any]] = []
        for provider_key, config in self.provider_registry.list_providers().items():
            provider_name = provider_key.lower()
            is_available = self._provider_available(provider_name)
            models_registry = config.get("models", {})
            models_detail = {}
            for model_name in models_registry.keys():
                try:
                    models_detail[model_name] = self.get_llm_info(provider_name, model_name)
                except ValueError:
                    models_detail[model_name] = {
                        "provider": provider_name,
                        "model": model_name,
                        "name": models_registry[model_name].get("name", model_name),
                        "description": models_registry[model_name].get("description", ""),
                    }

            providers.append(
                {
                    "provider": provider_name,
                    "name": config.get("name", provider_name),
                    "available": is_available,
                    "default_model": config.get("default_model"),
                    "models": list(models_registry.keys()),
                    "api_key_required": config.get("api_key_env"),
                    "mode_defaults": dict(config.get("mode_defaults", {})),
                    "models_detail": models_detail,
                }
            )
        return providers

    def get_provider_models(self, provider: Union[str, LLMProvider]) -> Dict[str, Any]:
        """Return raw model registry for a provider."""
        provider_key, _ = self._normalise_provider(provider)
        config = self._get_provider_config(provider_key)
        return config.get("models", {})

    def get_llm_info(
        self,
        provider: Union[str, LLMProvider],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return enriched model information."""
        provider_key, _ = self._normalise_provider(provider)
        try:
            info = self.provider_registry.get_model_info(provider_key, model)
        except ValueError:
            # For providers with dynamic models (e.g., Ollama) fall back to defaults.
            resolved_model = model or self._get_provider_config(provider_key).get("default_model")
            info = {
                "provider": provider_key.lower(),
                "model": resolved_model,
                "name": resolved_model,
                "description": "",
                "recommended": False,
                "model_features": [],
                "supports_tools": False,
                "max_tokens": None,
                "context_window": None,
                "mode_defaults": {
                    "llm": self._get_provider_config(provider_key).get("mode_defaults", {}).get("llm", {})
                },
            }
        info["available"] = self._provider_available(info["provider"])
        return info

    def set_api_key(self, provider: Union[str, LLMProvider], api_key: str) -> None:
        """Set or override provider API key."""
        if not api_key:
            raise ValueError("API key must not be empty")
        provider_key, provider_enum = self._normalise_provider(provider)
        if provider_enum == LLMProvider.OLLAMA:
            logger.info("OLLAMA does not require an API key, ignoring provided value")
            return
        self._api_keys[provider_enum] = api_key
        logger.info("API key set for provider %s", provider_key)

    def get_recommended_models(self) -> List[Dict[str, Any]]:
        """Return recommended models for all available providers."""
        recommendations: List[Dict[str, Any]] = []
        for provider_key, config in self.provider_registry.list_providers().items():
            for model_name, model_config in config.get("models", {}).items():
                if model_config.get("recommended"):
                    try:
                        info = self.get_llm_info(provider_key.lower(), model_name)
                        if info.get("available"):
                            recommendations.append(
                                {
                                    "provider": info["provider"],
                                    "provider_name": info.get("provider_name", config.get("name")),
                                    "model": info["model"],
                                    "model_name": info.get("model_name", model_config.get("name", model_name)),
                                    "description": info.get("description", ""),
                                }
                            )
                    except ValueError:
                        continue
        return recommendations

    # Internal helpers

    def _normalise_provider(
        self,
        provider: Union[str, LLMProvider],
    ) -> Tuple[str, LLMProvider]:
        if isinstance(provider, LLMProvider):
            return provider.value.upper(), provider
        provider_name = str(provider).lower()
        provider_enum = LLMProvider(provider_name)
        return provider_enum.value.upper(), provider_enum

    def _get_provider_config(self, provider_key: str) -> Dict[str, Any]:
        config = self.provider_registry.get_provider_config(provider_key)
        if not config:
            raise ValueError(f"Provider {provider_key} not found")
        return config

    def _resolve_model_name(self, provider_config: Dict[str, Any], model: Optional[str]) -> str:
        if model:
            return model
        default_model = provider_config.get("default_model")
        if not default_model:
            raise ValueError("Provider configuration does not define a default model")
        return default_model

    def _create_adapter(self, provider_key: str, model: str, mode: str):
        adapter_cls = self._adapter_map.get(provider_key)
        if not adapter_cls:
            raise ValueError(f"No adapter registered for provider {provider_key}")
        return adapter_cls(model=model, provider_registry=self.provider_registry, mode=mode)

    def _create_instance(self, provider_key: str, params: Dict[str, Any]):
        instance_cls = self._instance_map.get(provider_key)
        if not instance_cls:
            raise ValueError(f"No instance registered for provider {provider_key}")
        return instance_cls(**params)

    def _prepare_instance_params(
        self,
        provider_key: str,
        provider_enum: LLMProvider,
        adapter,
        adapter_params: Dict[str, Any],
        explicit_api_key: Optional[str],
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        params = adapter_params.copy()
        params.setdefault("model", adapter.model)

        if provider_enum == LLMProvider.OLLAMA:
            base_url = params.get("base_url") or user_params.get("base_url") or settings.ollama_base_url
            params["base_url"] = base_url
            params.setdefault("timeout", user_params.get("timeout") or settings.ollama_timeout)
            params.setdefault("keep_alive", user_params.get("keep_alive") or settings.ollama_keep_alive)
        else:
            api_key = self._resolve_api_key(provider_enum, explicit_api_key)
            params["api_key"] = api_key
            if provider_enum == LLMProvider.OPENAI:
                base_url = params.get("base_url") or user_params.get("base_url") or settings.openai_base_url
                if base_url:
                    params["base_url"] = base_url

        return params

    def _resolve_api_key(self, provider_enum: LLMProvider, explicit_api_key: Optional[str]) -> str:
        if explicit_api_key:
            return explicit_api_key
        cached = self._api_keys.get(provider_enum)
        if cached:
            return cached
        provider_key = provider_enum.value.upper()
        provider_config = self._get_provider_config(provider_key)
        env_name = provider_config.get("api_key_env", "API_KEY")
        raise ValueError(f"API key for provider {provider_enum.value} not configured. Please set environment {env_name}")

    def _provider_available(self, provider_name: str) -> bool:
        if provider_name == LLMProvider.OLLAMA.value:
            return True
        provider_enum = LLMProvider(provider_name)
        return provider_enum in self._api_keys


# Global manager instance
llm_manager = LLMManager()


# Convenience functions
def get_available_providers() -> List[Dict[str, Any]]:
    return llm_manager.get_available_providers()


async def create_llm(provider: str, model: str = None, **kwargs):
    return await llm_manager.create_llm(provider, model, **kwargs)


def get_llm_info(provider: str, model: str = None) -> Dict[str, Any]:
    return llm_manager.get_llm_info(provider, model)


def get_recommended_models() -> List[Dict[str, Any]]:
    return llm_manager.get_recommended_models()


def reload_llm_config() -> bool:
    return llm_manager.reload_config()
