"""Ollama agent adapter using LangChain 1.0 agent graphs."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent

from .base import AgentAdapter
from src.components.shared.memory.checkpointer import BaseAgentCheckpointer
from src.core.providers.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class OllamaAgentAdapter(AgentAdapter):
    """Ollama agent adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        super().__init__("OLLAMA", model, provider_registry=provider_registry)

    def get_agent_params(self, **user_params: Dict[str, Any]) -> Dict[str, Any]:
        """Collect Ollama agent parameters."""
        params = super().get_agent_params(**user_params)
        params.setdefault("max_iterations", 3)
        params.setdefault("max_execution_time", 30)
        logger.debug("Ollama agent params: %s", params)
        return params

    def create_agent_graph(
        self,
        llm: Any,
        tools: Sequence[Any],
        *,
        checkpointer: Optional[BaseAgentCheckpointer] = None,
        **params: Any,
    ):
        """Create the CompiledStateGraph for Ollama models."""
        agent_params = self.get_agent_params(**params)

        system_prompt = (
            "Answer user questions as accurately as possible. You may call tools to "
            "collect information or execute actions. Think through each step and "
            "produce a clear final answer."
        )

        graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer.checkpointer if checkpointer else None,
        )

        logger.info(
            "CompiledStateGraph created for provider=%s model=%s max_iterations=%s max_execution_time=%s",
            self.provider,
            self.model,
            agent_params.get("max_iterations"),
            agent_params.get("max_execution_time"),
        )

        return graph

    def supports_function_calling(self) -> bool:
        """Return Ollama function calling capability."""
        return False

    def get_agent_type(self) -> str:
        """Return the default agent type."""
        return "react"
