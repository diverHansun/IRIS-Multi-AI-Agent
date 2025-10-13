"""
智谱AI代理模块

智谱AI Agent实现，专注于GLM-4-plus的ReAct功能。
使用外置模板系统和JSON ReAct解析器，支持工具调用和记忆管理。
"""

import logging
from typing import Optional, Dict, Any

from src.llm.langchain.instances.zhipu_llm import create_zhipu_llm

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ZhipuAgent(BaseAgent):
    """Zhipu AI Agent - Specialized for GLM models with ReAct functionality."""

    def __init__(self,
                 model: str = "glm-4-plus",
                 temperature: float = 0.1,
                 verbose: bool = False,
                 max_iterations: int = 8,
                 enable_memory: bool = True,
                 memory_config: Optional[Dict[str, Any]] = None,
                 global_memory_manager = None,
                 prompt_provider: Optional[str] = None):
        """
        Initialize Zhipu AI Agent.

        Args:
            model: Zhipu AI model name
            temperature: Temperature parameter
            verbose: Enable verbose logging
            max_iterations: Maximum iterations
            enable_memory: Enable memory management
            memory_config: Memory configuration parameters
            global_memory_manager: Global memory manager
            prompt_provider: Prompt template provider
        """
        # Call parent constructor
        super().__init__(
            model=model,
            temperature=temperature,
            verbose=verbose,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
            memory_config=memory_config,
            global_memory_manager=global_memory_manager
        )

        # Zhipu-specific configuration
        self.prompt_provider = prompt_provider or ("glm" if "glm" in model.lower() else None)

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """使用 LLM Adapter 参数创建 LLM（新接口）"""
        self.llm = create_zhipu_llm(
            model=llm_params.get("model", self.model),
            temperature=llm_params.get("temperature", 0.1),
            max_tokens=llm_params.get("max_tokens", 2048),
            streaming=llm_params.get("streaming", False),
            thinking_mode=llm_params.get("thinking_mode", False)
        )

        logger.info(f"LLM 创建完成（新方式）: {self.model}, params: {llm_params}")

    def _get_provider_name(self) -> str:
        """Get provider name for agent info."""
        return "zhipu"