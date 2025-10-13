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
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        verbose: bool = False,
        enable_memory: bool = True,
        global_memory_manager = None,
        **kwargs
    ):
        """
        Initialize OpenAI Agent.

        Args:
            api_key: OpenAI API key
            model: Model name
            temperature: Temperature parameter
            verbose: Enable verbose logging
            enable_memory: Enable memory management
            global_memory_manager: Global memory manager
            **kwargs: Additional parameters
        """
        # Call parent constructor
        super().__init__(
            model=model,
            temperature=temperature,
            verbose=verbose,
            enable_memory=enable_memory,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        # OpenAI-specific configuration
        self.api_key = api_key

        logger.info(f"Creating OpenAI Agent instance: {model}")

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """使用 LLM Adapter 参数创建 LLM（新接口）"""
        from src.config import settings

        base_url = self.kwargs.get('base_url') or settings.openai_base_url
        
        # 使用新的LLM管理器创建LLM
        llm_kwargs = {
            "api_key": self.api_key,
            "model": llm_params.get("model", self.model),
            "temperature": llm_params.get("temperature", 0.1),
            "streaming": llm_params.get("streaming", False)
        }
        
        if base_url:
            llm_kwargs["base_url"] = base_url
        
        if "max_tokens" in llm_params and llm_params["max_tokens"] is not None:
            llm_kwargs["max_tokens"] = llm_params["max_tokens"]

        self.llm = llm_manager.create_llm(
            provider="openai",
            **llm_kwargs
        )

        logger.info(f"LLM 创建完成（新方式）: {self.model}")

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "openai"


