"""
Agent Factory Registry

工厂注册表，用于管理和查找不同Provider的Agent工厂。
"""

import logging
from typing import Dict, Optional

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory

logger = logging.getLogger(__name__)


class FactoryRegistry:
    """Agent工厂注册表"""

    def __init__(self, auto_register_defaults: bool = True):
        """
        初始化工厂注册表

        Args:
            auto_register_defaults: 是否自动注册默认工厂
        """
        self._factories: Dict[str, BaseAgentFactory] = {}

        if auto_register_defaults:
            self._register_default_factories()

    def _register_default_factories(self) -> None:
        """注册默认工厂"""
        self.register_factory("ZHIPU", ZhipuAgentFactory())
        self.register_factory("OPENAI", OpenAIAgentFactory())
        self.register_factory("OLLAMA", OllamaAgentFactory())
        logger.debug("已注册默认Agent工厂: ZHIPU, OPENAI, OLLAMA")

    def register_factory(self, provider: str, factory: BaseAgentFactory) -> None:
        """
        注册工厂

        Args:
            provider: 提供商名称
            factory: 工厂实例
        """
        provider_key = provider.upper()
        self._factories[provider_key] = factory
        logger.debug(f"已注册Agent工厂: {provider_key} -> {factory.__class__.__name__}")

    def get_factory(self, provider: str) -> Optional[BaseAgentFactory]:
        """
        获取工厂

        Args:
            provider: 提供商名称

        Returns:
            工厂实例，如果未找到返回None
        """
        provider_key = provider.upper()
        factory = self._factories.get(provider_key)

        if factory is None:
            logger.warning(f"未找到Provider '{provider_key}' 的Agent工厂")

        return factory

    def has_factory(self, provider: str) -> bool:
        """
        判断是否存在工厂

        Args:
            provider: 提供商名称

        Returns:
            是否存在
        """
        return provider.upper() in self._factories

    def get_all_providers(self) -> list:
        """获取所有已注册的Provider"""
        return list(self._factories.keys())

    def __repr__(self) -> str:
        providers = ', '.join(self._factories.keys())
        return f"FactoryRegistry(providers=[{providers}])"


# 全局单例
_global_registry: Optional[FactoryRegistry] = None


def get_global_registry() -> FactoryRegistry:
    """
    获取全局工厂注册表单例

    Returns:
        全局FactoryRegistry实例
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = FactoryRegistry(auto_register_defaults=True)
        logger.debug("创建全局Agent工厂注册表")

    return _global_registry


def reset_global_registry() -> None:
    """重置全局工厂注册表（主要用于测试）"""
    global _global_registry
    _global_registry = None
    logger.debug("已重置全局Agent工厂注册表")
