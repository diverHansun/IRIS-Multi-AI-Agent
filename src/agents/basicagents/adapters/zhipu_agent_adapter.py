"""Zhipu agent adapter responsible for prompt selection and graph creation."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent

from .base import AgentAdapter
from src.components.basicagents.prompts.registry import PromptRegistry
from src.components.shared.memory.checkpointer import BaseAgentCheckpointer
from src.core.providers.provider_registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ZhipuAgentAdapter(AgentAdapter):
    """Zhipu agent adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        super().__init__("ZHIPU", model, provider_registry=provider_registry)

    def get_agent_params(self, **user_params: Dict[str, Any]) -> Dict[str, Any]:
        """Collect Zhipu agent parameters."""
        params = super().get_agent_params(**user_params)
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            logger.debug(
                "Model %s using configured max_iterations=%s",
                self.model,
                params.get("max_iterations"),
            )
        return params

    def create_agent_graph(
        self,
        llm: Any,
        tools: Sequence[Any],
        *,
        checkpointer: Optional[BaseAgentCheckpointer] = None,
        **params: Any,
    ):
        """Create the CompiledStateGraph for Zhipu models."""
        agent_params = self.get_agent_params(**params)

        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            logger.info("Model %s using Tool Calling prompt", self.model)
            template_text = PromptRegistry.get_prompt(
                agent_type="tool_calling",
                provider="glm",
                locale="zh_CN",
            )
        else:
            logger.info("Model %s using ReAct prompt", self.model)
            template_text = PromptRegistry.get_prompt(
                agent_type="react_json",
                provider="glm",
                locale="zh_CN",
            )

        system_prompt = self._convert_template_to_system_prompt(template_text)

        graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=checkpointer.checkpointer if checkpointer else None,
        )

        logger.info(
            "CompiledStateGraph created: provider=%s model=%s max_iterations=%s max_execution_time=%s",
            self.provider,
            self.model,
            agent_params.get("max_iterations"),
            agent_params.get("max_execution_time"),
        )

        return graph

    def _convert_template_to_system_prompt(self, template_text: str) -> str:
        """Convert legacy template text into a concise system prompt."""
        return (
            "You are a helpful assistant. Use the available tools when necessary and "
            "provide clear, direct answers when a tool call is not required."
        )

    def supports_function_calling(self) -> bool:
        """Return whether the model supports function calling."""
        return self.model in ["glm-4.5", "glm-4.5-flash"]

    def get_agent_type(self) -> str:
        """Return the preferred agent type."""
        return "function_calling" if self.supports_function_calling() else "react"
