"""OpenAI agent adapter implementing LangChain agent graph creation."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .base import AgentAdapter
from src.components.shared.memory.checkpointer import BaseAgentCheckpointer
from src.core.providers.basicagents_provider_registry import BasicAgentsProviderRegistry

logger = logging.getLogger(__name__)


class OpenAIAgentAdapter(AgentAdapter):
    """OpenAI agent adapter using ChatOpenAI."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[BasicAgentsProviderRegistry] = None,
    ):
        """
        Initialize OpenAI agent adapter.

        Args:
            model: Model name. If None, uses default model
            provider_registry: Optional custom registry instance
        """
        super().__init__("openai", model, provider_registry=provider_registry)

    def _create_llm_instance(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        llm_params: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> ChatOpenAI:
        """
        Create ChatOpenAI instance.

        OpenAI can use custom base_url for proxy/alternative endpoints.

        Args:
            api_key: OpenAI API key from environment
            base_url: API base URL (from config or env override)
            llm_params: LLM parameters (temperature, max_tokens, etc.)
            user_params: Additional user parameters

        Returns:
            ChatOpenAI instance

        Raises:
            ValueError: If API key is not provided
        """
        if not api_key:
            raise ValueError("OpenAI API key is required but not found in environment")

        # Build ChatOpenAI parameters
        openai_params = {
            "model": llm_params["model"],
            "openai_api_key": api_key,
            "streaming": llm_params.get("streaming", False),
        }

        # Add base_url if provided (for proxy/alternative endpoints)
        if base_url:
            openai_params["base_url"] = base_url
            logger.debug(f"Using custom base_url: {base_url}")

        # Add optional parameters
        if llm_params.get("temperature") is not None:
            # Handle temperature_fixed for GPT-5 models
            if self._config.get("temperature_fixed"):
                fixed_temp = self._config.get("temperature", 1.0)
                openai_params["temperature"] = fixed_temp
                if llm_params["temperature"] != fixed_temp:
                    logger.warning(
                        "Model %s enforces temperature=%s (user input %s ignored)",
                        self.model,
                        fixed_temp,
                        llm_params["temperature"],
                    )
            else:
                openai_params["temperature"] = llm_params["temperature"]

        if llm_params.get("max_tokens") is not None:
            openai_params["max_tokens"] = llm_params["max_tokens"]

        logger.debug(f"Creating ChatOpenAI with params: {openai_params.keys()}")

        return ChatOpenAI(**openai_params)

    def get_agent_params(self, **user_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect OpenAI specific agent parameters.

        Args:
            **user_params: User-provided parameter overrides

        Returns:
            Merged agent parameters
        """
        params = super().get_agent_params(**user_params)
        logger.debug("OpenAI agent params: %s", params)
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
        Create the CompiledStateGraph for OpenAI models.

        Args:
            llm: ChatOpenAI instance
            tools: List of tools
            checkpointer: Optional checkpointer for memory
            **params: Additional parameters

        Returns:
            CompiledStateGraph instance
        """
        agent_params = self.get_agent_params(**params)

        system_prompt = (
            "You are a helpful assistant. Use the provided tools when necessary to "
            "produce accurate and concise answers. Explain tool usage briefly and "
            "reply directly when no tool call is required."
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
        """
        OpenAI models support function calling.

        Returns:
            True (all OpenAI models support function calling)
        """
        return True

    def get_agent_type(self) -> str:
        """
        Return the default agent type.

        Returns:
            "function_calling"
        """
        return "function_calling"
