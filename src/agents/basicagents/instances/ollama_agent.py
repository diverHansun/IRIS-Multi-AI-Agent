"""Ollama agent implementation built on BaseAgent."""

import logging
from typing import Any, Dict, Optional

from src.llm.managers import llm_manager

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class OllamaAgent(BaseAgent):
    """Ollama agent supporting locally hosted models."""

    def __init__(
        self,
        model: str = "gpt-oss:20b",
        provider: str = "ollama",
        llm_adapter: Optional[Any] = None,
        agent_adapter: Optional[Any] = None,
        global_memory_manager: Optional[Any] = None,
        base_url: str = "http://localhost:11434",
        disable_thinking_mode: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            provider=provider,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            global_memory_manager=global_memory_manager,
            **kwargs,
        )
        self.base_url = base_url
        self.disable_thinking_mode = disable_thinking_mode
        logger.info("Creating Ollama agent instance: %s", model)

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """Create the Ollama LLM with processed parameters."""
        params = llm_params.copy()
        params.setdefault("base_url", self.base_url)
        params.setdefault("disable_thinking_mode", self.disable_thinking_mode)

        for key, value in self.kwargs.items():
            if value is not None and key not in params:
                params[key] = value

        if params.get("base_url"):
            self.base_url = params["base_url"]
        if params.get("temperature") is not None:
            self.temperature = params["temperature"]

        model_name = params.pop("model", self.model)
        self.model = model_name

        llm = llm_manager.create_llm(
            provider="ollama",
            model=model_name,
            mode="agent",
            **params,
        )

        logger.info("Ollama LLM created: %s (%s)", model_name, params)
        return llm

    def _get_provider_name(self) -> str:
        """Return provider identifier used by info lookups."""
        return "ollama"
