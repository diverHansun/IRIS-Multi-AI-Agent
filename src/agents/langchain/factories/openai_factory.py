"""
OpenAI Agent Factory

OpenAI Agent工厂，统一创建OpenAI Agent。
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseAgentFactory

logger = logging.getLogger(__name__)


class OpenAIAgentFactory(BaseAgentFactory):
    """OpenAI Agent工厂"""

    def __init__(self):
        super().__init__(provider="OPENAI")

    async def create_agent(
        self,
        model: str,
        verbose: bool = False,
        temperature: Optional[float] = None,
        enable_memory: bool = True,
        global_memory_manager = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        创建OpenAI Agent

        Args:
            model: 模型名称
            verbose: 是否详细输出
            temperature: 温度参数（GPT-5会被适配器处理）
            enable_memory: 是否启用记忆
            global_memory_manager: 全局记忆管理器
            api_key: OpenAI API密钥
            **kwargs: 其他参数

        Returns:
            OpenAIAgent实例
        """
        from src.agents.langchain.instances.openai_agent import build_openai_agent

        logger.info(f"创建OpenAI Agent: {model}")

        agent = await build_openai_agent(
            api_key=api_key,
            model=model,
            verbose=verbose,
            temperature=temperature,
            enable_memory=enable_memory,
            global_memory_manager=global_memory_manager,
            **kwargs
        )

        logger.info(f"成功创建OpenAI Agent: {model}")
        return agent
