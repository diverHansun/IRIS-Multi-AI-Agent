"""
Refactored OpenAI agent adapter.

Handles OpenAI-specific LLM creation, graph creation, and agent instantiation.
"""

import logging
from typing import List, Optional

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agents.basicagents.adapters.base import AgentAdapter
from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.exceptions import LLMCreationError, GraphCreationError
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class OpenAIAgentAdapter(AgentAdapter):
    """
    OpenAI agent adapter using ChatOpenAI.

    Handles OpenAI-specific features:
    - temperature_fixed for models that enforce specific temperature
    - Custom base_url support for proxies/alternative endpoints
    - System prompt configuration
    """

    def __init__(
        self,
        config: AgentConfig,
        shared_checkpointer: Optional[UnifiedCheckpointer] = None,
    ):
        """
        Initialize OpenAI agent adapter.

        Args:
            config: Fully resolved AgentConfig instance
        """
        super().__init__(config, shared_checkpointer=shared_checkpointer)

    def create_llm(self) -> BaseChatModel:
        """
        Create ChatOpenAI instance.

        Uses config.llm_params for all parameters.
        Handles temperature_fixed if specified in provider_specific.

        Returns:
            ChatOpenAI instance

        Raises:
            LLMCreationError: If LLM creation fails
        """
        try:
            llm_params = self.config.llm_params

            # Build ChatOpenAI parameters
            openai_params = {
                "model": llm_params["model"],
                "openai_api_key": llm_params["api_key"],
                "streaming": llm_params.get("streaming", False),
            }

            # Add base_url if provided (for proxy/alternative endpoints)
            if llm_params.get("base_url"):
                openai_params["base_url"] = llm_params["base_url"]
                logger.debug(f"Using custom base_url: {llm_params['base_url']}")

            # Handle temperature (check for temperature_fixed)
            if llm_params.get("temperature") is not None:
                if self.config.provider_specific.get("temperature_fixed"):
                    # Model enforces a fixed temperature
                    fixed_temp = llm_params["temperature"]
                    openai_params["temperature"] = fixed_temp
                    logger.info(
                        f"Model {self.model} enforces temperature={fixed_temp} "
                        "(temperature_fixed=true)"
                    )
                else:
                    openai_params["temperature"] = llm_params["temperature"]

            # Add max_tokens if provided
            if llm_params.get("max_tokens") is not None:
                openai_params["max_tokens"] = llm_params["max_tokens"]

            logger.debug(f"Creating ChatOpenAI with params: {list(openai_params.keys())}")

            return ChatOpenAI(**openai_params)

        except Exception as e:
            raise LLMCreationError(
                provider=self.provider,
                model=self.model,
                reason=str(e)
            ) from e

    def create_graph(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
    ) -> CompiledStateGraph:
        """
        Create agent graph for OpenAI models.

        Uses system_prompt from config.provider_specific.
        Falls back to default prompt if not configured.

        Args:
            llm: ChatOpenAI instance
            tools: List of tools
            checkpointer: UnifiedCheckpointer instance or None

        Returns:
            Compiled state graph

        Raises:
            GraphCreationError: If graph creation fails
        """
        try:
            # Get system_prompt from config (no hardcoded prompts)
            system_prompt = self.config.provider_specific.get("system_prompt")

            if not system_prompt:
                # Fallback to default prompt
                system_prompt = (
                    "You are a helpful assistant. Use the provided tools when necessary to "
                    "produce accurate and concise answers. Explain tool usage briefly and "
                    "reply directly when no tool call is required."
                )
                logger.debug("Using default system prompt (no prompt configured)")

            logger.debug(f"Creating graph with system_prompt length: {len(system_prompt)}")

            graph = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt,
                checkpointer=checkpointer if checkpointer else None,
            )

            logger.info(
                f"Graph created for {self.provider}/{self.model} "
                f"(agent_type={self.config.agent_params.get('agent_type')})"
            )

            return graph

        except Exception as e:
            raise GraphCreationError(
                provider=self.provider,
                model=self.model,
                reason=str(e)
            ) from e

    def _instantiate_agent(
        self,
        llm: BaseChatModel,
        graph: CompiledStateGraph,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
    ):
        """
        Instantiate OpenAI agent.

        Returns OpenAIAgent instance.

        Args:
            llm: ChatOpenAI instance
            graph: Compiled state graph
            tools: List of tools
            checkpointer: UnifiedCheckpointer instance or None

        Returns:
            OpenAIAgent instance
        """
        from src.agents.basicagents.instances import OpenAIAgent

        logger.debug(f"Using OpenAIAgent for {self.model}")

        # Create agent with all initialized components
        return OpenAIAgent(
            provider=self.config.provider,
            model=self.config.model,
            llm=llm,
            graph=graph,
            tools=tools,
            checkpointer=checkpointer,
            config=self.config,
        )
