"""Zhipu AI agent implementation built on BaseAgent."""

import logging
from typing import Any, Dict, Optional

from src.llm.managers import llm_manager

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ZhipuAgent(BaseAgent):
    """Zhipu agent specialising in GLM models with tool usage support."""

    def __init__(
        self,
        model: str = "glm-4-plus",
        provider: str = "zhipu",
        llm_adapter: Optional[Any] = None,
        agent_adapter: Optional[Any] = None,
        memory_config: Optional[Dict[str, Any]] = None,
        global_memory_manager: Optional[Any] = None,
        prompt_provider: Optional[str] = None,
    ):
        super().__init__(
            model=model,
            provider=provider,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            memory_config=memory_config,
            global_memory_manager=global_memory_manager,
        )
        self.prompt_provider = prompt_provider or ("glm" if "glm" in model.lower() else None)

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """Create the Zhipu LLM with processed parameters."""
        params = llm_params.copy()
        model_name = params.pop("model", self.model)
        self.model = model_name

        if params.get("temperature") is not None:
            self.temperature = params["temperature"]

        llm = await llm_manager.create_llm(
            provider="zhipu",
            model=model_name,
            mode="agent",
            **params,
        )

        logger.info("Zhipu LLM created: %s (%s)", model_name, params)
        return llm

    def _get_provider_name(self) -> str:
        """Return provider identifier used by info lookups."""
        return "zhipu"
