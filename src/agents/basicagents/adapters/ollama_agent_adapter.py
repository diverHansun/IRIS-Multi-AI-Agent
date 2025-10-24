"""Ollama agent adapter using LangChain agent graphs."""

import logging
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from .base import AgentAdapter
from src.components.shared.memory.checkpointer import BaseAgentCheckpointer
from src.core.providers.basicagents_provider_registry import BasicAgentsProviderRegistry

logger = logging.getLogger(__name__)


class OllamaAgentAdapter(AgentAdapter):
    """Ollama agent adapter using ChatOpenAI with local endpoint."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[BasicAgentsProviderRegistry] = None,
    ):
        """
        Initialize Ollama agent adapter.

        Args:
            model: Model name. If None, uses default model
            provider_registry: Optional custom registry instance
        """
        super().__init__("OLLAMA", model, provider_registry=provider_registry)

    def _create_llm_instance(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        llm_params: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> ChatOpenAI:
        """
        Create ChatOpenAI instance for Ollama local endpoint.

        Ollama does not require API key, uses local base_url.

        Args:
            api_key: Not used for Ollama
            base_url: Local Ollama endpoint (e.g., http://localhost:11434)
            llm_params: LLM parameters (temperature, max_tokens, etc.)
            user_params: Additional user parameters

        Returns:
            ChatOpenAI instance configured for Ollama

        Raises:
            ValueError: If base_url is not provided
        """
        if not base_url:
            raise ValueError(
                "Ollama requires base_url but none was configured. "
                "Please set OLLAMA_BASE_URL in .env or configure in providers.json"
            )

        # Build ChatOpenAI parameters for Ollama
        ollama_params = {
            "model": llm_params["model"],
            "base_url": base_url,
            "api_key": "ollama",  # Ollama doesn't need real API key but ChatOpenAI requires it
            "streaming": llm_params.get("streaming", False),
        }

        # Add optional parameters
        if llm_params.get("temperature") is not None:
            ollama_params["temperature"] = llm_params["temperature"]

        if llm_params.get("max_tokens") is not None:
            ollama_params["max_tokens"] = llm_params["max_tokens"]

        # Add Ollama-specific extra params
        extra_params = self._config.get("extra_params", {})
        if "timeout" in extra_params:
            ollama_params["timeout"] = extra_params["timeout"]

        logger.debug(f"Creating ChatOpenAI for Ollama with base_url: {base_url}")

        return ChatOpenAI(**ollama_params)

    def get_agent_params(self, **user_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect Ollama agent parameters.

        Ollama typically uses lower iteration limits due to local execution.

        Args:
            **user_params: User-provided parameter overrides

        Returns:
            Merged agent parameters
        """
        params = super().get_agent_params(**user_params)

        # Ensure sensible defaults for local models
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
        """
        Create the CompiledStateGraph for Ollama models.

        Args:
            llm: ChatOpenAI instance configured for Ollama
            tools: List of tools
            checkpointer: Optional checkpointer for memory
            **params: Additional parameters

        Returns:
            CompiledStateGraph instance
        """
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
        """
        Return Ollama function calling capability.

        Most Ollama models use ReAct pattern rather than function calling.

        Returns:
            False (Ollama typically uses ReAct)
        """
        return False

    def get_agent_type(self) -> str:
        """
        Return the default agent type.

        Returns:
            "react"
        """
        return "react"
