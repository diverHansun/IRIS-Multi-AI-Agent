"""
Agent Factory - 智能Agent工厂

统一创建和管理不同LLM提供商的Agent实例
支持动态切换和配置管理
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Union
from enum import Enum

from .zhipu_agent import build_zhipu_agent, ZhipuAgent
from .openai_agent import build_openai_agent, OpenAIAgent
from .ollama_agent import build_ollama_agent, OllamaAgent
from ...llm.langchain.llm_manager import LLMManager, LLMProvider
from ...config import settings

logger = logging.getLogger(__name__)

class AgentFactory:
    """Agent工厂类"""
    
    def __init__(self):
        """初始化Agent工厂"""
        self.llm_manager = LLMManager()
        self._cached_agents = {}  # Agent缓存
        
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
        
        # 创建Agent
        logger.info(f"正在创建{provider.value} Agent: {model}")
        
        try:
            if provider == LLMProvider.ZHIPU:
                # glm-4.5 和 glm-4.5-flash 使用原生 Function Calling Agent，其余保持 ReAct
                if model in ["glm-4.5", "glm-4.5-flash"]:
                    from .zhipu_fcall_agent import build_zhipu_fcall_agent
                    agent = await build_zhipu_fcall_agent(
                        model=model,
                        verbose=verbose,
                        temperature=temperature,
                        enable_memory=enable_memory,
                        global_memory_manager=global_memory_manager,
                        **kwargs
                    )
                    if use_cache:
                        self._cached_agents[cache_key] = agent
                    logger.info(f"成功创建{provider.value} Agent: {model}")
                    return agent
                agent = await build_zhipu_agent(
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    # 基于提供商选择模板：ZHIPU 对应 GLM 模板族
                    prompt_provider="glm",
                    **kwargs
                )
            
            elif provider == LLMProvider.OPENAI:
                # GPT-5模型特殊处理：使用固定temperature=1.0
                if model.startswith("gpt-5"):
                    logger.info(f"GPT-5模型({model})使用默认temperature=1.0")
                    actual_temperature = 1.0
                else:
                    actual_temperature = temperature
                
                agent = await build_openai_agent(
                    api_key=api_key,
                    model=model,
                    verbose=verbose,
                    temperature=actual_temperature,
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    **kwargs
                )
            
            elif provider == LLMProvider.OLLAMA:
                # Ollama模型参数处理 - 针对Agent模式优化
                base_url = kwargs.get('base_url', settings.ollama_base_url)
                
                # 如果model为"auto"，则使用本地第一个可用模型
                if model == "auto":
                    try:
                        from ...llm.langchain.ollama_utils import list_ollama_models
                        local_models = await list_ollama_models(base_url, timeout=5)
                        if local_models:
                            model = local_models[0]  # 使用第一个本地模型
                            logger.info(f"自动选择Ollama模型: {model}")
                        else:
                            # 如果没有本地模型，使用默认值
                            model = "gpt-oss:20b"
                            logger.warning("未找到本地Ollama模型，使用默认模型: gpt-oss:20b")
                    except Exception as e:
                        # 出错时回退到默认模型
                        model = "gpt-oss:20b"
                        logger.warning(f"获取Ollama模型列表失败，使用默认模型: gpt-oss:20b, 错误: {e}")
                
                # Agent模式强制使用低温度，除非用户显式指定
                agent_temperature = 0.0 if temperature == 0.1 else temperature
                
                agent = await build_ollama_agent(
                    model=model,
                    base_url=base_url,
                    verbose=verbose,
                    temperature=agent_temperature,  # 使用优化的温度
                    enable_memory=enable_memory,
                    global_memory_manager=global_memory_manager,
                    disable_thinking_mode=kwargs.get('disable_thinking_mode', True),  # 默认关闭思考模式
                    **{k: v for k, v in kwargs.items() if k != 'disable_thinking_mode'}
                )
            
            else:
                raise ValueError(f"不支持的LLM提供商: {provider}")
            
            # 缓存Agent
            if use_cache:
                self._cached_agents[cache_key] = agent
            
            logger.info(f"成功创建{provider.value} Agent: {model}")
            return agent
            
        except Exception as e:
            logger.error(f"创建{provider.value} Agent失败: {str(e)}")
            raise
    
    def get_available_configurations(self) -> Dict[str, Any]:
        """获取可用的Agent配置"""
        from ...config import settings
        
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
