"""
OpenAI Agent Implementation

基于OpenAI GPT模型的智能Agent实现
支持完整的工具集成和记忆功能
"""

import logging
from typing import Dict, Any, Optional, Iterable

from src.llm.langchain.managers import llm_manager

from .base_agent import BaseAgent

__all__ = [
    # 数学工具
    "add_numbers", "calculate_math",
    # 搜索工具
    "get_available_search_tools", "get_available_tavily_tools",
    # 时间工具
    "get_available_time_tools",
    # 高德地图工具
    "get_available_amap_tools",
    # Notion工具
    "get_available_notion_tools",
    # OKX工具
    "get_available_okx_tools",
    # 工具管理器
    "SDKToolManager",
    "ConnectorToolManager"
]

# OKX工具可用性 - 通过工具管理器处理
OKX_AVAILABLE = True  # 由SDKToolManager统一管理

logger = logging.getLogger(__name__)


def _format_exception(e: Exception) -> str:
    """Render rich details for ExceptionGroup/TaskGroup to aid debugging."""
    try:
        if hasattr(e, "exceptions") and isinstance(getattr(e, "exceptions"), Iterable):
            parts = [f"{e.__class__.__name__}: {e}"]
            for idx, se in enumerate(getattr(e, "exceptions")):
                parts.append(f"  [{idx}] {se.__class__.__name__}: {se}")
            return "\n".join(parts)
    except Exception:
        pass
    return f"{e.__class__.__name__}: {e}"

class OpenAIAgent(BaseAgent):
    """OpenAI Agent - Function Calling based implementation."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        provider: str = "openai",
        llm_adapter = None,
        agent_adapter = None,
        global_memory_manager = None,
        **kwargs
    ):
        """
        Initialize OpenAI Agent.

        Args:
            model: Model name
            provider: Provider name
            llm_adapter: LLM adapter
            agent_adapter: Agent adapter
            global_memory_manager: Global memory manager
            **kwargs: Additional parameters
        """
        # Call parent constructor
        super().__init__(
            model=model,
            provider=provider,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        logger.info(f"Creating OpenAI Agent instance: {model}")

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """Create LLM instance using processed parameters."""
        params = llm_params.copy()
        model_name = params.pop("model", self.model)
        self.model = model_name

        if "temperature" in params and params["temperature"] is not None:
            self.temperature = params["temperature"]

        llm = llm_manager.create_llm(
            provider="openai",
            model=model_name,
            mode="agent",
            **params,
        )

        logger.info("LLM created via adapter: %s, params=%s", model_name, llm_params)
        return llm

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "openai"
