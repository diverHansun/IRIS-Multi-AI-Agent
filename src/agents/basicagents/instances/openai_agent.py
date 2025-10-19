"""OpenAI agent implementation built on BaseAgent."""

import logging
from typing import Any, Dict, Optional

from src.llm.managers import llm_manager

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class OpenAIAgent(BaseAgent):
    """OpenAI agent implementation configured for function calling."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        llm_adapter: Optional[Any] = None,
        agent_adapter: Optional[Any] = None,
        global_memory_manager: Optional[Any] = None,
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
        logger.info("Creating OpenAI agent instance: %s", model)

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """Create the OpenAI LLM with processed parameters."""
        params = llm_params.copy()
        model_name = params.pop("model", self.model)
        self.model = model_name

        if params.get("temperature") is not None:
            self.temperature = params["temperature"]

        llm = llm_manager.create_llm(
            provider="openai",
            model=model_name,
            mode="agent",
            **params,
        )

        logger.info("OpenAI LLM created: %s (%s)", model_name, params)
        return llm

    def _get_provider_name(self) -> str:
        """Return provider identifier used by info lookups."""
        return "openai"
