"""
Zhipu AI agent implementation.

Specialized agent for Zhipu GLM models using ReAct pattern.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from langgraph.checkpoint.memory import MemorySaver

from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.instances.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ZhipuAgent(BaseAgent):
    """
    Zhipu agent for GLM models using ReAct pattern.

    Supports all GLM models (glm-4-plus, glm-4.5, glm-4.5-flash, etc.)
    with standard ReAct reasoning pattern.
    """

    def __init__(
        self,
        provider: str,
        model: str,
        llm: BaseChatModel,
        graph: CompiledStateGraph,
        tools: List[BaseTool],
        checkpointer: Optional[MemorySaver],
        config: AgentConfig,
    ):
        """
        Initialize Zhipu agent with fully initialized components.

        Args:
            provider: Provider name (should be 'zhipu')
            model: Model name (e.g., 'glm-4-plus', 'glm-4.5-flash')
            llm: Initialized ChatZhipuAI instance
            graph: Compiled state graph
            tools: List of tools
            checkpointer: Memory checkpointer for runtime state (None if memory disabled)
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

        logger.info(f"ZhipuAgent initialized for model: {model}")

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
            "agent_type": self.config.agent_params.get("agent_type", "react"),
            "thinking_mode": self.config.provider_specific.get("thinking_mode", False),
        }

    def get_llm(self) -> BaseChatModel:
        """Return the LLM instance for external use."""
        return self.llm

    def _get_provider_name(self) -> str:
        """
        Get provider identifier.

        Returns:
            Provider name string ('zhipu')
        """
        return self.provider