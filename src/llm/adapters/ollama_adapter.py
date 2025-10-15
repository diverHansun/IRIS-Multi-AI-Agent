"""
Ollama LLM Adapter.

Applies provider defaults and Ollama specific adjustments such as temperature
optimisation for agent mode and convenience flags.
"""

import logging
from typing import Any, Dict, Optional

from src.core.providers.provider_registry import ProviderRegistry
from src.core.providers.utils import list_ollama_models

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):
    """Ollama LLM adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
        mode: str = "llm",
    ):
        super().__init__(
            provider="OLLAMA",
            model=model,
            provider_registry=provider_registry,
            mode=mode,
        )

    def get_llm_params(self, **kwargs: Any) -> Dict[str, Any]:
        """Return processed parameters for Ollama LLM."""
        params = self.get_base_params()

        if self.mode == "agent":
            user_temp = kwargs.get("temperature")
            if user_temp is None or user_temp == 0.1:
                params["temperature"] = 0.0
                logger.debug("Ollama agent mode temperature adjusted to 0.0")
            else:
                params["temperature"] = user_temp

        if "disable_thinking_mode" not in kwargs:
            params["disable_thinking_mode"] = True

        user_params = kwargs.copy()
        if self.mode == "agent":
            user_params.pop("temperature", None)

        params = self.merge_user_params(params, user_params)
        params.setdefault("model", self.model)

        logger.debug("Ollama %s (%s) params: %s", self.model, self.mode, params)
        return params

    async def resolve_auto_model(self, base_url: str) -> str:
        """Resolve actual model name when configured as 'auto'."""
        if self.model != "auto":
            return self.model

        try:
            local_models = await list_ollama_models(base_url, timeout=5)
        except Exception as exc:
            logger.warning("Failed to list Ollama models (%s), using fallback model", exc)
            local_models = []

        if local_models:
            selected = local_models[0]
            logger.info("Auto selected Ollama model: %s", selected)
            return selected

        fallback = "gpt-oss:20b"
        logger.warning("No local Ollama models found, using fallback %s", fallback)
        return fallback
