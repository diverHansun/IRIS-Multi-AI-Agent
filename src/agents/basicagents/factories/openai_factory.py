"""
OpenAI Agent Factory

OpenAI Agent工厂，统一创建OpenAI Agent。
"""

import logging
import warnings
from typing import Dict, Any, Optional

from .base import BaseAgentFactory

logger = logging.getLogger(__name__)


class OpenAIAgentFactory(BaseAgentFactory):
    """OpenAI Agent工厂"""

    def __init__(self):
        super().__init__(provider="openai")

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

        .. deprecated:: 4.0
            使用 agent_manager.create_agent() 替代。
            此方法将在 v5.0 中移除。

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
        import warnings
        warnings.warn(
            "OpenAIAgentFactory.create_agent() is deprecated. "
            "Use agent_manager.create_agent() instead. "
            "Will be removed in v5.0.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "OpenAIAgentFactory.create_agent() is deprecated. "
            "Use agent_manager.create_agent('openai', model) instead."
        )

    async def create_agent_with_adapters(
        self,
        model: str,
        llm_adapter,
        agent_adapter,
        **user_params
    ) -> Any:
        """
        创建Agent实例（新接口，使用Adapters）

        这是推荐的创建方式，由AgentManager调用。
        使用adapters提供的配置驱动参数管理。

        Args:
            model: 模型名称
            llm_adapter: LLM适配器
            agent_adapter: Agent适配器
            **user_params: 用户参数（可覆盖配置）

        Returns:
            OpenAIAgent实例
        """
        from src.agents.basicagents.instances import OpenAIAgent

        logger.info(f"创建OpenAI Agent (新模式): {model}")

        # 创建Agent实例（传入adapters）
        agent = OpenAIAgent(
            provider="openai",
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **user_params
        )

        # 初始化
        await agent.initialize()

        logger.info(f"成功创建OpenAI Agent (新模式): {model}")
        return agent