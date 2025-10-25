"""Zhipu agent adapter responsible for LLM creation and graph creation."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent
from langchain_community.chat_models import ChatZhipuAI

from .base import AgentAdapter
from src.components.basicagents.prompts.registry import PromptRegistry
from src.components.shared.memory.checkpointer import BaseAgentCheckpointer
from src.core.providers.basicagents_provider_registry import BasicAgentsProviderRegistry

logger = logging.getLogger(__name__)


class ZhipuAgentAdapter(AgentAdapter):
    """Zhipu agent adapter using official ChatZhipuAI SDK."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[BasicAgentsProviderRegistry] = None,
    ):
        """
        Initialize Zhipu agent adapter.

        Args:
            model: Model name. If None, uses default model
            provider_registry: Optional custom registry instance
        """
        super().__init__("zhipu", model, provider_registry=provider_registry)

    def _create_llm_instance(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        llm_params: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> ChatZhipuAI:
        """
        Create ChatZhipuAI instance using official SDK.

        Zhipu uses official SDK, does not need base_url.

        Args:
            api_key: Zhipu API key from environment
            base_url: Not used for Zhipu (official SDK)
            llm_params: LLM parameters (temperature, max_tokens, etc.)
            user_params: Additional user parameters

        Returns:
            ChatZhipuAI instance

        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("Zhipu API key is required but not found in environment")

        # Build ChatZhipuAI parameters
        zhipu_params = {
            "model": llm_params["model"],
            "zhipuai_api_key": api_key,
            "streaming": llm_params.get("streaming", False),
        }

        # Add optional parameters
        if llm_params.get("temperature") is not None:
            zhipu_params["temperature"] = llm_params["temperature"]

        if llm_params.get("max_tokens") is not None:
            zhipu_params["max_tokens"] = llm_params["max_tokens"]

        # Add thinking_mode for glm-4.5 models
        if self._config.get("thinking_mode"):
            zhipu_params["thinking"] = True
            logger.debug(f"Model {self.model} using thinking_mode=True")

        logger.debug(f"Creating ChatZhipuAI with params: {zhipu_params.keys()}")

        return ChatZhipuAI(**zhipu_params)

    def get_agent_params(self, **user_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect Zhipu agent parameters.

        Args:
            **user_params: User-provided parameter overrides

        Returns:
            Merged agent parameters
        """
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
        """
        Create the CompiledStateGraph for Zhipu models.

        Args:
            llm: ChatZhipuAI instance
            tools: List of tools
            checkpointer: Optional checkpointer for memory
            **params: Additional parameters

        Returns:
            CompiledStateGraph instance
        """
        agent_params = self.get_agent_params(**params)

        # Select appropriate prompt based on model capabilities
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
        """
        Convert legacy template text into a concise system prompt.

        Args:
            template_text: Template text from prompt registry

        Returns:
            System prompt string
        """
        return (
            "You are a helpful assistant. Use the available tools when necessary and "
            "provide clear, direct answers when a tool call is not required."
        )

    def supports_function_calling(self) -> bool:
        """
        Return whether the model supports function calling.

        Returns:
            True if model supports function calling, False otherwise
        """
        return self.model in ["glm-4.5", "glm-4.5-flash"]

    def get_agent_type(self) -> str:
        """
        Return the preferred agent type.

        Returns:
            "function_calling" or "react"
        """
        return "function_calling" if self.supports_function_calling() else "react"
