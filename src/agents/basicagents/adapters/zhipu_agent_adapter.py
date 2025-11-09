"""
Refactored Zhipu agent adapter.

Handles Zhipu-specific LLM creation, graph creation, and agent instantiation.
"""

import logging
from typing import List, Optional

from langchain.agents import create_agent
from langchain_community.chat_models import ChatZhipuAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agents.basicagents.adapters.base import AgentAdapter
from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.exceptions import LLMCreationError, GraphCreationError
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class ZhipuAgentAdapter(AgentAdapter):
    """
    Zhipu agent adapter using official ChatZhipuAI SDK.

    Handles Zhipu-specific features:
    - thinking_mode for glm-4.5 models
    - Model-based agent type selection (react vs function_calling)
    - System prompt configuration
    """

    def __init__(
        self,
        config: AgentConfig,
        shared_checkpointer: Optional[UnifiedCheckpointer] = None,
    ):
        """
        Initialize Zhipu agent adapter.

        Args:
            config: Fully resolved AgentConfig instance
        """
        super().__init__(config, shared_checkpointer=shared_checkpointer)

    def create_llm(self) -> BaseChatModel:
        """
        Create ChatZhipuAI instance.

        Uses config.llm_params for all parameters.
        Applies thinking_mode if specified in provider_specific.

        Returns:
            ChatZhipuAI instance

        Raises:
            LLMCreationError: If LLM creation fails
        """
        try:
            llm_params = self.config.llm_params

            # Build ChatZhipuAI parameters
            zhipu_params = {
                "model": llm_params["model"],
                "zhipuai_api_key": llm_params["api_key"],
                "streaming": llm_params.get("streaming", False),
            }

            # Add optional parameters (no hardcoded defaults)
            if llm_params.get("temperature") is not None:
                zhipu_params["temperature"] = llm_params["temperature"]

            if llm_params.get("max_tokens") is not None:
                zhipu_params["max_tokens"] = llm_params["max_tokens"]

            # Zhipu-specific: thinking_mode
            if self.config.provider_specific.get("thinking_mode"):
                zhipu_params["thinking"] = True
                logger.debug(f"Model {self.model} using thinking_mode")

            logger.debug(f"Creating ChatZhipuAI with params: {list(zhipu_params.keys())}")

            return ChatZhipuAI(**zhipu_params)

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
        Create agent graph for Zhipu models.

        Uses system_prompt from config.provider_specific.
        Falls back to default prompt if not configured.

        Args:
            llm: ChatZhipuAI instance
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
                    "You are a helpful assistant. Use the available tools when necessary "
                    "and provide clear, direct answers when a tool call is not required."
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
        Instantiate Zhipu agent.

        Selects agent class based on agent_type:
        - function_calling -> ZhipuFCallAgent
        - react -> ZhipuAgent

        Args:
            llm: ChatZhipuAI instance
            graph: Compiled state graph
            tools: List of tools
            checkpointer: UnifiedCheckpointer instance or None

        Returns:
            ZhipuAgent or ZhipuFCallAgent instance
        """
        from src.agents.basicagents.instances import ZhipuAgent, ZhipuFCallAgent

        # Select agent class based on agent_type from config
        agent_type = self.config.agent_params.get("agent_type", "react")

        if agent_type == "function_calling":
            agent_class = ZhipuFCallAgent
            logger.debug(f"Using ZhipuFCallAgent for {self.model}")
        else:
            agent_class = ZhipuAgent
            logger.debug(f"Using ZhipuAgent for {self.model}")

        # Create agent with all initialized components
        return agent_class(
            provider=self.config.provider,
            model=self.config.model,
            llm=llm,
            graph=graph,
            tools=tools,
            checkpointer=checkpointer,
            config=self.config,
        )
