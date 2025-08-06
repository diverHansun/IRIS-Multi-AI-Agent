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
from ..llm.llm_manager import LLMManager, LLMProvider
from ..config import settings

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
        **kwargs
    ) -> Union[ZhipuAgent, OpenAIAgent]:
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
        
        # 检查缓存
        cache_key = f"{provider.value}_{model}_{temperature}_{enable_memory}"
        if use_cache and cache_key in self._cached_agents:
            logger.info(f"使用缓存的Agent: {provider.value}/{model}")
            return self._cached_agents[cache_key]
        
        # 获取API密钥
        if not api_key:
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
                agent = await build_zhipu_agent(
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    **kwargs
                )
            
            elif provider == LLMProvider.OPENAI:
                agent = await build_openai_agent(
                    api_key=api_key,
                    model=model,
                    verbose=verbose,
                    temperature=temperature,
                    enable_memory=enable_memory,
                    **kwargs
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
        providers = self.llm_manager.get_available_providers()
        
        configurations = {
            "available_providers": [],
            "recommended_configs": [],
            "default_config": None
        }
        
        for provider_info in providers:
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
        
        # 设置默认配置
        if configurations["available_providers"]:
            # 优先使用智谱AI
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
) -> Union[ZhipuAgent, OpenAIAgent]:
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


async def create_default_agent(**kwargs) -> Union[ZhipuAgent, OpenAIAgent]:
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