"""
Agent Factory - 智能Agent工厂

统一创建和管理不同LLM提供商的Agent实例
支持动态切换和配置管理

重构说明：
- 内部使用FactoryRegistry实现抽象工厂模式
- 保持所有现有API和行为向后兼容
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Union
from enum import Enum

from .instances.zhipu_agent import build_zhipu_agent, ZhipuAgent
from .instances.openai_agent import build_openai_agent, OpenAIAgent
from .instances.ollama_agent import build_ollama_agent, OllamaAgent
from src.llm.langchain.managers import LLMManager, LLMProvider
from src.config import settings

# 导入Factory Registry
from .factories import get_global_registry

logger = logging.getLogger(__name__)

class AgentFactory:
    """Agent工厂类（使用Registry模式重构）"""

    def __init__(self, use_registry: bool = True):
        """
        初始化Agent工厂

        Args:
            use_registry: 是否使用工厂注册表（默认True）
        """
        self.llm_manager = LLMManager()
        self._cached_agents = {}  # Agent缓存
        self.use_registry = use_registry

        # 获取全局Registry
        if self.use_registry:
            self._registry = get_global_registry()
            logger.debug("AgentFactory使用Registry模式")
        
    async def create_agent(
        self,
        provider: Union[str, LLMProvider],
        model: str = None,
        verbose: bool = False,
        temperature: float = 0.1,
        enable_memory: bool = True,
        api_key: str = None,
        use_cache: bool = True,
        global_memory_manager = None,
        **kwargs
    ) -> Union[ZhipuAgent, OpenAIAgent, OllamaAgent]:
        """
        创建Agent实例
        
        Args:
            provider: LLM提供商 ("zhipu" 或 "openai")
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
        # 标准化provider
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        # 获取默认模型
        if not model:
            config = self.llm_manager.SUPPORTED_LLMS[provider]
            model = config["default_model"]
        
        # 验证模型是否受支持（除了Ollama，它可以动态加载模型）
        if provider != LLMProvider.OLLAMA:
            try:
                self.llm_manager.get_llm_info(provider, model)
            except ValueError as e:
                raise ValueError(str(e))  # 重新抛出模型不支持的错误
        
        # 检查缓存
        cache_key = f"{provider.value}_{model}_{temperature}_{enable_memory}"
        if use_cache and cache_key in self._cached_agents:
            logger.info(f"使用缓存的Agent: {provider.value}/{model}")
            return self._cached_agents[cache_key]
        
        # 获取API密钥（Ollama不需要API密钥）
        if provider != LLMProvider.OLLAMA and not api_key:
            if provider == LLMProvider.ZHIPU:
                api_key = settings.zhipu_api_key
            elif provider == LLMProvider.OPENAI:
                api_key = getattr(settings, 'openai_api_key', None)
            
            if not api_key:
                config = self.llm_manager.SUPPORTED_LLMS[provider]
                raise ValueError(f"未找到{config['name']}的API密钥，请设置环境变量 {config['api_key_env']}")
        
        # 创建Agent（使用Registry模式）
        logger.info(f"正在创建{provider.value} Agent: {model}")

        try:
            if self.use_registry:
                # 使用Registry创建Agent
                factory = self._registry.get_factory(provider.value)

                if factory is None:
                    raise ValueError(f"不支持的LLM提供商: {provider}")

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

            else:
                # 回退到原始if-else逻辑（向后兼容）
                agent = await self._create_agent_legacy(
                    provider=provider,
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    api_key=api_key,
                    **kwargs
                )

            # 缓存Agent
            if use_cache:
                self._cached_agents[cache_key] = agent

            logger.info(f"成功创建{provider.value} Agent: {model}")
            return agent

        except Exception as e:
            logger.error(f"创建{provider.value} Agent失败: {str(e)}")
            raise

    async def _create_agent_legacy(
        self,
        provider: LLMProvider,
        model: str,
        verbose: bool,
        temperature: float,
        enable_memory: bool,
        global_memory_manager,
        api_key: Optional[str],
        **kwargs
    ):
        """
        Legacy Agent创建逻辑（保留用于回退）

        这是原始的if-else创建逻辑，用于向后兼容
        """
        if provider == LLMProvider.ZHIPU:
            # glm-4.5 和 glm-4.5-flash 使用原生 Function Calling Agent
            if model in ["glm-4.5", "glm-4.5-flash"]:
                from .instances.zhipu_fcall_agent import build_zhipu_fcall_agent
                return await build_zhipu_fcall_agent(
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    **kwargs
                )
            else:
                return await build_zhipu_agent(
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    prompt_provider="glm",
                    **kwargs
                )

        elif provider == LLMProvider.OPENAI:
            # GPT-5模型特殊处理
            if model.startswith("gpt-5"):
                logger.info(f"GPT-5模型({model})使用默认temperature=1.0")
                actual_temperature = 1.0
            else:
                actual_temperature = temperature

            return await build_openai_agent(
                api_key=api_key,
                model=model,
                verbose=verbose,
                temperature=actual_temperature,
                enable_memory=enable_memory,
                global_memory_manager=global_memory_manager,
                **kwargs
            )

        elif provider == LLMProvider.OLLAMA:
            base_url = kwargs.get('base_url', settings.ollama_base_url)

            # auto模型选择
            if model == "auto":
                try:
                    from src.llm.langchain.utils import list_ollama_models
                    local_models = await list_ollama_models(base_url, timeout=5)
                    if local_models:
                        model = local_models[0]
                        logger.info(f"自动选择Ollama模型: {model}")
                    else:
                        model = "gpt-oss:20b"
                        logger.warning("未找到本地Ollama模型，使用默认模型: gpt-oss:20b")
                except Exception as e:
                    model = "gpt-oss:20b"
                    logger.warning(f"获取Ollama模型列表失败，使用默认模型: gpt-oss:20b, 错误: {e}")

            # Agent模式温度优化
            agent_temperature = 0.0 if temperature == 0.1 else temperature

            return await build_ollama_agent(
                model=model,
                base_url=base_url,
                verbose=verbose,
                temperature=agent_temperature,
                enable_memory=enable_memory,
                global_memory_manager=global_memory_manager,
                disable_thinking_mode=kwargs.get('disable_thinking_mode', True),
                **{k: v for k, v in kwargs.items() if k != 'disable_thinking_mode'}
            )
    
    def get_available_configurations(self) -> Dict[str, Any]:
        """获取可用的Agent配置"""
        from src.config import settings
        
        providers = self.llm_manager.get_available_providers()
        
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
                if default_model and self.llm_manager.validate_model(default_provider, default_model):
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


# 全局Agent工厂实例
agent_factory = AgentFactory()


# 便捷函数
async def create_agent(
    provider: str,
    model: str = None,
    verbose: bool = False,
    temperature: float = 0.1,
    **kwargs
) -> Union[ZhipuAgent, OpenAIAgent, OllamaAgent]:
    """创建Agent的便捷函数"""
    return await agent_factory.create_agent(
        provider=provider,
        model=model,
        verbose=verbose,
        temperature=temperature,
        **kwargs
    )


def get_available_configurations() -> Dict[str, Any]:
    """获取可用配置的便捷函数"""
    return agent_factory.get_available_configurations()


async def create_default_agent(**kwargs) -> Union[ZhipuAgent, OpenAIAgent, OllamaAgent]:
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


# 快速创建函数
async def create_zhipu_agent(model: str = "glm-4-plus", **kwargs) -> ZhipuAgent:
    """快速创建智谱AI Agent"""
    return await create_agent(provider="zhipu", model=model, **kwargs)


async def create_openai_agent(model: str = "gpt-4o-mini", **kwargs) -> OpenAIAgent:
    """快速创建OpenAI Agent"""
    return await create_agent(provider="openai", model=model, **kwargs)


async def create_ollama_agent(model: str = "gpt-oss:20b", **kwargs) -> OllamaAgent:
    """快速创建Ollama Agent"""
    # 为Agent模式设置默认优化参数
    defaults = {
        "temperature": 0.0,  # Agent模式使用低温度
        "disable_thinking_mode": True,  # 关闭思考模式
    }
    # 用户传递的参数覆盖默认值
    defaults.update(kwargs)
    return await create_agent(provider="ollama", model=model, **defaults)
