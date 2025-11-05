"""
OpenAI agent implementation.

Specialized agent for OpenAI models using function calling.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.instances.base_agent import BaseAgent
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class OpenAIAgent(BaseAgent):
    """
    OpenAI agent for GPT models using function calling.

    Supports all OpenAI models (gpt-4o, gpt-4o-mini, gpt-5, etc.)
    with native function calling capabilities.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        llm: BaseChatModel,
        graph: CompiledStateGraph,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
        config: AgentConfig,
    ):
        """
        Initialize OpenAI agent with fully initialized components.

        Args:
            provider: Provider name (should be 'openai')
            model: Model name (e.g., 'gpt-4o', 'gpt-4o-mini')
            llm: Initialized ChatOpenAI instance
            graph: Compiled state graph
            tools: List of tools
            checkpointer: Unified checkpointer (None if memory disabled)
            config: Agent configuration
        """
        super().__init__(
            provider=provider,
            model=model,
            llm=llm,
            graph=graph,
            tools=tools,
            checkpointer=checkpointer,
            config=config,
        )

        logger.info(f"OpenAIAgent initialized for model: {model}")

    def get_info(self) -> Dict[str, Any]:
        """
        Return agent information for display and tracking.

        Returns:
            Dictionary containing agent metadata
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_iterations": self.max_iterations,
            "max_execution_time": self.max_execution_time,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            "agent_type": self.config.agent_params.get("agent_type", "function_calling"),
            "temperature_fixed": self.config.provider_specific.get("temperature_fixed", False),
        }

    def get_llm(self) -> BaseChatModel:
        """Return the LLM instance for external use."""
        return self.llm

    def _get_provider_name(self) -> str:
        """
        Get provider identifier.

        Returns:
            Provider name string ('openai')
        """
        return self.provider