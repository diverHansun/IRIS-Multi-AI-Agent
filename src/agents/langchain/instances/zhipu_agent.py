"""
智谱AI代理模块

智谱AI Agent实现，专注于GLM-4-plus的ReAct功能。
使用外置模板系统和JSON ReAct解析器，支持工具调用和记忆管理。
"""

import logging
from typing import Optional, Dict, Any

from src.llm.langchain.managers import llm_manager

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ZhipuAgent(BaseAgent):
    """Zhipu AI Agent - Specialized for GLM models with ReAct functionality."""

    def __init__(self,
                 model: str = "glm-4-plus",
                 provider: str = "zhipu",
                 llm_adapter = None,
                 agent_adapter = None,
                 memory_config: Optional[Dict[str, Any]] = None,
                 global_memory_manager = None,
                 prompt_provider: Optional[str] = None):
        """
        Initialize Zhipu AI Agent.

        Args:
            model: Zhipu AI model name
            provider: Provider name
            llm_adapter: LLM adapter
            agent_adapter: Agent adapter
            memory_config: Memory configuration parameters
            global_memory_manager: Global memory manager
            prompt_provider: Prompt template provider
        """
        # Call parent constructor
        super().__init__(
            model=model,
            provider=provider,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            memory_config=memory_config,
            global_memory_manager=global_memory_manager
        )

        # Zhipu-specific configuration
        self.prompt_provider = prompt_provider or ("glm" if "glm" in model.lower() else None)

    async def _create_llm_instance(self, llm_params: Dict[str, Any]):
        """使用 LLM Adapter 参数创建 LLM（新接口）"""
        self.llm = llm_manager.create_llm(
            provider="zhipu",
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

    def _build_agent_executor_with_adapter(self):
        """Build agent executor using agent adapter"""
        # This method is required by the new BaseAgent interface
        # Implementation will depend on the specific agent implementation
        if self.agent_adapter:
            super()._build_agent_executor_with_adapter()
        else:
            # Fallback behavior if no adapter is provided
            # Subclasses should implement their specific build logic
            logger.warning("No agent adapter provided, using default behavior")
            # Here we would implement agent-specific logic if needed
            pass