"""
Agent Builder

建造者模式实现，提供流式API用于构建Agent。
简化Agent创建过程，支持预设配置。
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_core.tools import BaseTool

from src.agents.langchain.factories import get_global_registry

logger = logging.getLogger(__name__)


class AgentBuilder:
    """Agent建造者，提供流式API"""

    def __init__(self):
        """初始化AgentBuilder"""
        self._provider: Optional[str] = None
        self._model: Optional[str] = None
        self._temperature: Optional[float] = None
        self._verbose: bool = False
        self._enable_memory: bool = True
        self._tools: Optional[List[BaseTool]] = None
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None
        self._global_memory_manager = None
        self._extra_params: Dict[str, Any] = {}

        # 获取全局registry
        self._registry = get_global_registry()

    def with_provider(self, provider: str) -> 'AgentBuilder':
        """
        设置LLM提供商

        Args:
            provider: 提供商名称 (ZHIPU, OPENAI, OLLAMA)

        Returns:
            self (支持链式调用)
        """
        self._provider = provider.upper()
        return self

    def with_model(self, model: str) -> 'AgentBuilder':
        """
        设置模型名称

        Args:
            model: 模型名称

        Returns:
            self (支持链式调用)
        """
        self._model = model
        return self

    def with_temperature(self, temperature: float) -> 'AgentBuilder':
        """
        设置温度参数

        Args:
            temperature: 温度值 (0.0-2.0)

        Returns:
            self (支持链式调用)
        """
        self._temperature = temperature
        return self

    def with_verbose(self, verbose: bool = True) -> 'AgentBuilder':
        """
        设置详细输出

        Args:
            verbose: 是否详细输出

        Returns:
            self (支持链式调用)
        """
        self._verbose = verbose
        return self

    def with_memory(self, enabled: bool = True, manager=None) -> 'AgentBuilder':
        """
        设置记忆功能

        Args:
            enabled: 是否启用记忆
            manager: 全局记忆管理器（可选）

        Returns:
            self (支持链式调用)
        """
        self._enable_memory = enabled
        if manager is not None:
            self._global_memory_manager = manager
        return self

    def with_tools(self, tools: List[BaseTool]) -> 'AgentBuilder':
        """
        设置工具列表

        Args:
            tools: 工具列表

        Returns:
            self (支持链式调用)
        """
        self._tools = tools
        return self

    def with_api_key(self, api_key: str) -> 'AgentBuilder':
        """
        设置API密钥

        Args:
            api_key: API密钥

        Returns:
            self (支持链式调用)
        """
        self._api_key = api_key
        return self

    def with_base_url(self, base_url: str) -> 'AgentBuilder':
        """
        设置基础URL（用于Ollama或自定义OpenAI端点）

        Args:
            base_url: 基础URL

        Returns:
            self (支持链式调用)
        """
        self._base_url = base_url
        return self

    def with_extra_params(self, **kwargs) -> 'AgentBuilder':
        """
        添加额外参数

        Args:
            **kwargs: 额外参数

        Returns:
            self (支持链式调用)
        """
        self._extra_params.update(kwargs)
        return self

    async def build(self) -> Any:
        """
        构建Agent实例

        Returns:
            Agent实例

        Raises:
            ValueError: 如果缺少必需参数
        """
        # 验证必需参数
        if not self._provider:
            raise ValueError("必须指定provider，使用with_provider()设置")

        if not self._model:
            raise ValueError("必须指定model，使用with_model()设置")

        # 获取对应的工厂
        factory = self._registry.get_factory(self._provider)
        if factory is None:
            raise ValueError(f"不支持的Provider: {self._provider}")

        # 准备参数
        kwargs = self._extra_params.copy()

        # 添加基础参数
        if self._api_key:
            kwargs['api_key'] = self._api_key
        if self._base_url:
            kwargs['base_url'] = self._base_url
        if self._tools:
            kwargs['tools'] = self._tools

        # 使用工厂创建Agent
        logger.info(f"使用Builder创建Agent: {self._provider}/{self._model}")

        agent = await factory.create_agent(
            model=self._model,
            verbose=self._verbose,
            temperature=self._temperature,
            enable_memory=self._enable_memory,
            global_memory_manager=self._global_memory_manager,
            **kwargs
        )

        logger.info(f"成功使用Builder创建Agent: {self._provider}/{self._model}")
        return agent

    def reset(self) -> 'AgentBuilder':
        """
        重置所有参数

        Returns:
            self (支持链式调用)
        """
        self._provider = None
        self._model = None
        self._temperature = None
        self._verbose = False
        self._enable_memory = True
        self._tools = None
        self._api_key = None
        self._base_url = None
        self._global_memory_manager = None
        self._extra_params = {}
        return self

    def __repr__(self) -> str:
        return (
            f"AgentBuilder(provider={self._provider}, model={self._model}, "
            f"temperature={self._temperature}, memory={self._enable_memory})"
        )
