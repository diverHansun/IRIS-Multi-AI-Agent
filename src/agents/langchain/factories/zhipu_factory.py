"""
Zhipu Agent Factory

智谱AI Agent工厂，处理ReAct和Function Calling两种Agent类型的创建。
"""

import logging
import warnings
from typing import Dict, Any, Optional

from .base import BaseAgentFactory

logger = logging.getLogger(__name__)


class ZhipuAgentFactory(BaseAgentFactory):
    """智谱AI Agent工厂"""

    def __init__(self):
        super().__init__(provider="ZHIPU")
        self._fcall_models = ["glm-4.5", "glm-4.5-flash"]

    async def create_agent(
        self,
        model: str,
        verbose: bool = False,
        temperature: Optional[float] = None,
        enable_memory: bool = True,
        global_memory_manager = None,
        **kwargs
    ) -> Any:
        """
        创建智谱AI Agent

        .. deprecated:: 4.0
            使用 agent_manager.create_agent() 替代。
            此方法将在 v5.0 中移除。

        根据模型选择Agent类型：
        - glm-4.5, glm-4.5-flash: 使用Function Calling Agent
        - 其他模型: 使用ReAct Agent

        Args:
            model: 模型名称
            verbose: 是否详细输出
            temperature: 温度参数
            enable_memory: 是否启用记忆
            global_memory_manager: 全局记忆管理器
            **kwargs: 其他参数

        Returns:
            ZhipuAgent或ZhipuFCallAgent实例
        """
        import warnings
        warnings.warn(
            "ZhipuAgentFactory.create_agent() is deprecated. "
            "Use agent_manager.create_agent() instead. "
            "Will be removed in v5.0.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "ZhipuAgentFactory.create_agent() is deprecated. "
            "Use agent_manager.create_agent('zhipu', model) instead."
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
            Agent实例
        """
        from src.agents.langchain.instances import ZhipuAgent, ZhipuFCallAgent

        # 根据模型选择Agent类型
        if model in self._fcall_models:
            agent_class = ZhipuFCallAgent
            logger.info(f"使用 ZhipuFCallAgent (Function Calling): {model}")
        else:
            agent_class = ZhipuAgent
            logger.info(f"使用 ZhipuAgent (ReAct): {model}")

        # 创建Agent实例（传入adapters）
        agent = agent_class(
            provider="zhipu",
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **user_params
        )

        # 初始化
        await agent.initialize()

        logger.info(f"成功创建智谱AI Agent (新模式): {model}")
        return agent

    def is_function_calling_model(self, model: str) -> bool:
        """判断是否为Function Calling模型"""
        return model in self._fcall_models