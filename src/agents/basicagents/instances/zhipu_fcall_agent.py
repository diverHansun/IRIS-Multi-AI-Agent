"""
Zhipu AI Function Calling agent implementation.

Specialized agent for Zhipu GLM-4.5 models with native function calling support.
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


class ZhipuFCallAgent(BaseAgent):
    """
    Zhipu function calling agent for GLM-4.5 models.

    Uses native function calling capabilities of glm-4.5 and glm-4.5-flash models.
    Optimized for tool usage with thinking mode support.
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
        Initialize Zhipu function calling agent with fully initialized components.

        Args:
            provider: Provider name (should be 'zhipu')
            model: Model name (should be 'glm-4.5' or 'glm-4.5-flash')
            llm: Initialized ChatZhipuAI instance
            graph: Compiled state graph
            tools: List of tools
            checkpointer: Memory checkpointer for runtime state (None if memory disabled)
            config: Agent configuration
        """
        # Validate model supports function calling
        if model not in ["glm-4.5", "glm-4.5-flash"]:
            logger.warning(
                f"Model {model} may not support native function calling. "
                "Recommended models: glm-4.5, glm-4.5-flash"
            )

        super().__init__(
            provider=provider,
            model=model,
            llm=llm,
            graph=graph,
            tools=tools,
            checkpointer=checkpointer,
            config=config,
        )

        logger.info(f"ZhipuFCallAgent initialized for model: {model}")

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
            "agent_type": "function_calling",
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