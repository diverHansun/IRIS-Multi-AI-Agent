"""
Agent Factory Registry

工厂注册表，用于管理和查找不同Provider的Agent工厂。
增强版：支持缓存、配置查询、便捷创建函数。
"""

import logging
from typing import Dict, Optional, Any, Union
from enum import Enum

from .base import BaseAgentFactory
from .zhipu_factory import ZhipuAgentFactory
from .openai_factory import OpenAIAgentFactory
from .ollama_factory import OllamaAgentFactory

logger = logging.getLogger(__name__)


class FactoryRegistry:
    """Agent工厂注册表（增强版）"""

    def __init__(self, auto_register_defaults: bool = True):
        """
        初始化工厂注册表

        Args:
            auto_register_defaults: 是否自动注册默认工厂
        """
        self._factories: Dict[str, BaseAgentFactory] = {}
        self._cached_agents: Dict[str, Any] = {}  # Agent缓存
        self._llm_manager = None  # LLMManager实例（延迟加载）

        if auto_register_defaults:
            self._register_default_factories()

    def _register_default_factories(self) -> None:
        """注册默认工厂"""
        self.register_factory("ZHIPU", ZhipuAgentFactory())
        self.register_factory("OPENAI", OpenAIAgentFactory())
        self.register_factory("OLLAMA", OllamaAgentFactory())
        logger.debug("已注册默认Agent工厂: ZHIPU, OPENAI, OLLAMA")

    def _get_llm_manager(self):
        """获取LLMManager实例（延迟加载）"""
        if self._llm_manager is None:
            from src.llm.langchain.managers import LLMManager
            self._llm_manager = LLMManager()
        return self._llm_manager

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

    async def create_agent(
        self,
        provider: Union[str, Any],
        model: str = None,
        verbose: bool = False,
        temperature: float = 0.1,
        enable_memory: bool = True,
        api_key: str = None,
        use_cache: bool = True,
        global_memory_manager = None,
        **kwargs
    ) -> Any:
        """
        创建Agent实例

        Args:
            provider: LLM提供商 ("zhipu", "openai", "ollama" 或 LLMProvider枚举)
            model: 模型名称，为None时使用默认模型
            verbose: 是否显示详细信息
            temperature: 温度参数
            enable_memory: 是否启用记忆功能
            api_key: API密钥，为None时使用配置中的密钥
            use_cache: 是否使用缓存
            global_memory_manager: 全局记忆管理器实例
            **kwargs: 其他参数

        Returns:
            初始化完成的Agent实例
        """
        from src.llm.langchain.managers import LLMProvider
        from src.config import settings

        # 标准化provider
        if isinstance(provider, str):
            provider_str = provider.upper()
        else:
            # 假设是LLMProvider枚举
            provider_str = provider.value.upper()

        # 获取LLMManager
        llm_manager = self._get_llm_manager()

        # 获取默认模型
        if not model:
            try:
                provider_enum = LLMProvider(provider_str.lower())
                config = llm_manager.SUPPORTED_LLMS[provider_enum]
                model = config["default_model"]
            except (ValueError, KeyError):
                raise ValueError(f"不支持的LLM提供商: {provider_str}")

        # 验证模型是否受支持（Ollama除外，它可以动态加载模型）
        if provider_str != "OLLAMA":
            try:
                provider_enum = LLMProvider(provider_str.lower())
                llm_manager.get_llm_info(provider_enum, model)
            except ValueError as e:
                raise ValueError(str(e))

        # 检查缓存
        cache_key = f"{provider_str}_{model}_{temperature}_{enable_memory}"
        if use_cache and cache_key in self._cached_agents:
            logger.info(f"使用缓存的Agent: {provider_str}/{model}")
            return self._cached_agents[cache_key]

        # 获取API密钥（Ollama不需要API密钥）
        if provider_str != "OLLAMA" and not api_key:
            if provider_str == "ZHIPU":
                api_key = settings.zhipu_api_key
            elif provider_str == "OPENAI":
                api_key = getattr(settings, 'openai_api_key', None)

            if not api_key:
                try:
                    provider_enum = LLMProvider(provider_str.lower())
                    config = llm_manager.SUPPORTED_LLMS[provider_enum]
                    raise ValueError(f"未找到{config['name']}的API密钥，请设置环境变量 {config['api_key_env']}")
                except ValueError:
                    raise ValueError(f"未找到{provider_str}的API密钥")

        # 获取工厂
        factory = self.get_factory(provider_str)
        if factory is None:
            raise ValueError(f"不支持的LLM提供商: {provider_str}")

        # 创建Agent
        logger.info(f"正在创建{provider_str} Agent: {model}")

        try:
            # 准备factory参数
            factory_kwargs = kwargs.copy()
            if api_key:
                factory_kwargs['api_key'] = api_key

            agent = await factory.create_agent(
                model=model,
                verbose=verbose,
                temperature=temperature,
                enable_memory=enable_memory,
                global_memory_manager=global_memory_manager,
                **factory_kwargs
            )

            # 缓存Agent
            if use_cache:
                self._cached_agents[cache_key] = agent

            logger.info(f"成功创建{provider_str} Agent: {model}")
            return agent

        except Exception as e:
            logger.error(f"创建{provider_str} Agent失败: {str(e)}")
            raise

    def get_available_configurations(self) -> Dict[str, Any]:
        """获取可用的Agent配置"""
        from src.config import settings

        llm_manager = self._get_llm_manager()
        providers = llm_manager.get_available_providers()

        configurations = {
            "available_providers": [],
            "recommended_configs": [],
            "default_config": None
        }

        # 构建提供商信息映射
        provider_map = {}
        for provider_info in providers:
            provider_map[provider_info["provider"]] = provider_info
            if provider_info["available"]:
                configurations["available_providers"].append(provider_info)

                # 添加推荐配置
                for model in provider_info.get("models_detail", {}).keys():
                    model_info = provider_info["models_detail"][model]
                    if model_info.get("recommended", False):
                        configurations["recommended_configs"].append({
                            "provider": provider_info["provider"],
                            "provider_name": provider_info["name"],
                            "model": model,
                            "model_name": model_info["name"],
                            "description": model_info["description"]
                        })

        # 设置默认配置，优先考虑环境变量设置
        if configurations["available_providers"]:
            # 检查环境变量中设置的默认提供商是否可用
            default_provider = settings.default_llm_provider
            default_model = settings.default_llm_model

            # 如果环境变量中的提供商可用
            if default_provider in provider_map and provider_map[default_provider]["available"]:
                provider_info = provider_map[default_provider]
                # 如果环境变量中设置了模型且该模型受支持，否则使用提供商的默认模型
                if default_model and llm_manager.validate_model(default_provider, default_model):
                    model_to_use = default_model
                else:
                    model_to_use = provider_info["default_model"]

                configurations["default_config"] = {
                    "provider": default_provider,
                    "model": model_to_use
                }
            else:
                # 回退到原来的逻辑：优先使用智谱AI
                zhipu_provider = next(
                    (p for p in configurations["available_providers"] if p["provider"] == "zhipu"),
                    None
                )
                if zhipu_provider:
                    configurations["default_config"] = {
                        "provider": "zhipu",
                        "model": zhipu_provider["default_model"]
                    }
                else:
                    # 使用第一个可用的提供商
                    first_provider = configurations["available_providers"][0]
                    configurations["default_config"] = {
                        "provider": first_provider["provider"],
                        "model": first_provider["default_model"]
                    }

        return configurations

    def clear_cache(self):
        """清除Agent缓存"""
        self._cached_agents.clear()
        logger.info("已清除Agent缓存")

    def get_cached_agents(self) -> Dict[str, Any]:
        """获取缓存的Agent信息"""
        cache_info = {}
        for cache_key, agent in self._cached_agents.items():
            info = agent.get_info()
            cache_info[cache_key] = {
                "provider": info.get("provider"),
                "model": info.get("model"),
                "initialized": info.get("initialized"),
                "tool_count": info.get("tool_count")
            }
        return cache_info

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


# ========== 便捷函数 ==========

async def create_agent(
    provider: str,
    model: str = None,
    verbose: bool = False,
    temperature: float = 0.1,
    **kwargs
) -> Any:
    """创建Agent的便捷函数"""
    registry = get_global_registry()
    return await registry.create_agent(
        provider=provider,
        model=model,
        verbose=verbose,
        temperature=temperature,
        **kwargs
    )


def get_available_configurations() -> Dict[str, Any]:
    """获取可用配置的便捷函数"""
    registry = get_global_registry()
    return registry.get_available_configurations()


async def create_default_agent(**kwargs) -> Any:
    """创建默认Agent"""
    configs = get_available_configurations()
    default_config = configs.get("default_config")

    if not default_config:
        raise RuntimeError("没有可用的LLM配置，请检查API密钥设置")

    return await create_agent(
        provider=default_config["provider"],
        model=default_config["model"],
        **kwargs
    )


async def create_zhipu_agent(model: str = "glm-4-plus", **kwargs) -> Any:
    """快速创建智谱AI Agent"""
    return await create_agent(provider="zhipu", model=model, **kwargs)


async def create_openai_agent(model: str = "gpt-4o-mini", **kwargs) -> Any:
    """快速创建OpenAI Agent"""
    return await create_agent(provider="openai", model=model, **kwargs)


async def create_ollama_agent(model: str = "gpt-oss:20b", **kwargs) -> Any:
    """快速创建Ollama Agent"""
    # 为Agent模式设置默认优化参数
    defaults = {
        "temperature": 0.0,  # Agent模式使用低温度
        "disable_thinking_mode": True,  # 关闭思考模式
    }
    # 用户传递的参数覆盖默认值
    defaults.update(kwargs)
    return await create_agent(provider="ollama", model=model, **defaults)
