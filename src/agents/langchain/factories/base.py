"""
Agent Factory Base Class

抽象工厂模式基类，用于创建不同类型的Agent。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseAgentFactory(ABC):
    """Agent工厂抽象基类"""

    def __init__(self, provider: str):
        """
        初始化Agent工厂

        Args:
            provider: LLM提供商名称 (ZHIPU, OPENAI, OLLAMA)
        """
        self.provider = provider.upper()

    @abstractmethod
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
        创建Agent实例

        Args:
            model: 模型名称
            verbose: 是否详细输出
            temperature: 温度参数
            enable_memory: 是否启用记忆
            global_memory_manager: 全局记忆管理器
            **kwargs: 其他参数

        Returns:
            Agent实例
        """
        pass

    async def create_agent_with_adapters(
        self,
        model: str,
        llm_adapter,
        agent_adapter,
        **user_params
    ) -> Any:
        """
        Create agent with adapters (new interface, recommended)

        This method is called by AgentManager and receives pre-created adapters.
        Default implementation calls create_agent() for backward compatibility.
        Subclasses can override this method for optimized implementation.

        Args:
            model: Model name
            llm_adapter: LLM adapter instance
            agent_adapter: Agent adapter instance
            **user_params: User parameters

        Returns:
            Agent instance
        """
        # Default implementation: delegate to old create_agent method
        # Subclasses should override this with optimized implementation
        return await self.create_agent(model=model, **user_params)

    def supports_model(self, model: str) -> bool:
        """
        判断工厂是否支持指定模型

        默认实现：总是返回True
        子类可以覆盖此方法提供更具体的判断逻辑

        Args:
            model: 模型名称

        Returns:
            是否支持
        """
        return True

    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return self.provider

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider})"
