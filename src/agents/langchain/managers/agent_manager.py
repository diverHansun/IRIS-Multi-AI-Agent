"""
Agent Manager - Agent创建和管理的统一入口

负责协调LLM和Agent的创建，应用配置参数。
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent管理器

    职责:
    - 协调Agent创建流程
    - 集成LLM Adapter和Agent Adapter
    - 应用配置文件中的agent参数
    """

    def __init__(self):
        """初始化Agent管理器"""
        # 使用共享provider_registry替代llm_manager
        from src.core.langchain.providers import provider_registry
        from src.agents.langchain.factories.registry import FactoryRegistry

        self.provider_registry = provider_registry
        self.factory_registry = FactoryRegistry()

        logger.info("AgentManager initialized")

    async def create_agent(
        self,
        provider: str,
        model: str = None,
        agent_type: str = "auto",
        **user_params
    ):
        """
        创建Agent实例

        Args:
            provider: Provider名称 (zhipu, openai, ollama)
            model: 模型名称，None时使用默认模型
            agent_type: Agent类型 ("auto", "react", "function_calling")
            **user_params: 用户自定义参数，可覆盖配置文件的默认值
                - temperature: 温度参数
                - max_iterations: 最大迭代次数
                - max_execution_time: 最大执行时间
                - enable_memory: 是否启用记忆
                - verbose: 是否详细输出
                等

        Returns:
            初始化完成的Agent实例

        Example:
            >>> from src.agents.langchain.managers import agent_manager
            >>> agent = agent_manager.create_agent(
            ...     provider="zhipu",
            ...     model="glm-4.5",
            ...     verbose=True
            ... )
        """
        provider = provider.upper()

        # 1. 获取Provider配置
        provider_config = self._get_provider_config(provider)
        if not model:
            model = provider_config.get("default_model")

        logger.info(f"Creating agent: {provider}/{model}")

        # 2. 创建LLM Adapter (来自llm模块)
        llm_adapter = self._create_llm_adapter(provider, model)

        # 3. 创建Agent Adapter (来自本模块)
        agent_adapter = self._create_agent_adapter(provider, model)

        # 4. 获取Factory并创建Agent
        factory = self.factory_registry.get_factory(provider)
        if not factory:
            raise ValueError(f"No factory found for provider: {provider}")

        # 使用Factory创建Agent（会调用create_agent_with_adapters）
        agent = await factory.create_agent_with_adapters(
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **user_params
        )

        logger.info(f"Agent created: {agent.__class__.__name__}")
        return agent

    def _get_provider_config(self, provider: str) -> Dict[str, Any]:
        """获取Provider配置"""
        try:
            # 从共享provider_registry获取配置
            config = self.provider_registry.get_provider_config(provider)
            if not config:
                raise ValueError(f"Provider {provider} not found")
            return config
        except Exception as e:
            logger.error(f"Failed to get provider config: {e}")
            raise

    def _create_llm_adapter(self, provider: str, model: str):
        """创建LLM适配器 (来自llm模块)"""
        from src.llm.langchain.adapters import (
            ZhipuAdapter,
            OpenAIAdapter,
            OllamaAdapter,
        )

        adapter_map = {
            "ZHIPU": ZhipuAdapter,
            "OPENAI": OpenAIAdapter,
            "OLLAMA": OllamaAdapter,
        }

        adapter_class = adapter_map.get(provider)
        if not adapter_class:
            raise ValueError(f"No LLM adapter found for provider: {provider}")

        return adapter_class(
            model=model,
            provider_registry=self.provider_registry,
            mode="agent",
        )

    def _create_agent_adapter(self, provider: str, model: str):
        """创建Agent适配器 (来自本模块)"""
        from src.agents.langchain.adapters import (
            ZhipuAgentAdapter,
            OpenAIAgentAdapter,
            OllamaAgentAdapter,
        )

        adapter_map = {
            "ZHIPU": ZhipuAgentAdapter,
            "OPENAI": OpenAIAgentAdapter,
            "OLLAMA": OllamaAgentAdapter,
        }

        adapter_class = adapter_map.get(provider)
        if not adapter_class:
            raise ValueError(f"No Agent adapter found for provider: {provider}")

        return adapter_class(
            model=model,
            provider_registry=self.provider_registry,
        )

    def _get_agent_class(self, provider: str, model: str, agent_type: str):
        """
        获取Agent类

        Args:
            provider: Provider名称
            model: 模型名称
            agent_type: Agent类型 ("auto", "react", "function_calling")

        Returns:
            Agent类
        """
        from src.agents.langchain.instances import (
            ZhipuAgent,
            ZhipuFCallAgent,
            OpenAIAgent,
            OllamaAgent,
        )

        # 自动选择Agent类型
        if agent_type == "auto":
            if provider == "ZHIPU":
                # glm-4.5系列使用Function Calling
                if model in ["glm-4.5", "glm-4.5-flash"]:
                    return ZhipuFCallAgent
                else:
                    return ZhipuAgent
            elif provider == "OPENAI":
                return OpenAIAgent
            elif provider == "OLLAMA":
                return OllamaAgent
            else:
                raise ValueError(f"Unknown provider: {provider}")

        # 手动指定Agent类型
        elif agent_type == "function_calling":
            if provider == "ZHIPU":
                return ZhipuFCallAgent
            elif provider == "OPENAI":
                return OpenAIAgent
            else:
                raise ValueError(f"Provider {provider} does not support function calling")

        elif agent_type == "react":
            if provider == "ZHIPU":
                return ZhipuAgent
            elif provider == "OPENAI":
                return OpenAIAgent
            elif provider == "OLLAMA":
                return OllamaAgent
            else:
                raise ValueError(f"Unknown provider: {provider}")

        else:
            raise ValueError(f"Unknown agent_type: {agent_type}")

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        获取可用的Agent列表

        Returns:
            可用Agent列表，包含provider、model、agent_type等信息
        """
        agents = []

        # 从provider_registry获取所有provider配置
        all_providers = self.provider_registry.list_providers()
        for provider_key, provider_config in all_providers.items():
            provider = provider_key.lower()
            models = provider_config.get("models", {})

            # 对于Ollama，需要动态检测本地可用模型
            if provider == "ollama":
                try:
                    # 动态获取Ollama本地模型
                    import asyncio
                    from src.core.langchain.providers.utils import list_ollama_models
                    
                    # 检查是否在事件循环中
                    try:
                        loop = asyncio.get_running_loop()
                        # 如果在事件循环中，创建新的线程来运行异步函数
                        import concurrent.futures
                        import threading
                        
                        def run_async():
                            return asyncio.run(list_ollama_models())
                        
                        # 在新线程中运行异步函数
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_async)
                            local_models = future.result(timeout=10)
                    except RuntimeError:
                        # 没有运行的事件循环，直接运行
                        local_models = asyncio.run(list_ollama_models())
                    
                    # 为每个本地模型创建一个代理项
                    for model_name in local_models:
                        agents.append({
                            "provider": provider,
                            "model": model_name,
                            "agent_type": "react",
                            "supports_tools": True,  # Ollama模型通常支持工具调用
                            "recommended": True,  # 本地模型视为推荐
                            "description": f"Ollama本地模型: {model_name}",
                        })
                    
                    # 如果没有本地模型，至少添加一个基础项
                    if not local_models:
                        agents.append({
                            "provider": provider,
                            "model": "default",
                            "agent_type": "react",
                            "supports_tools": True,
                            "recommended": False,
                            "description": "Ollama本地模型（无模型）",
                        })
                except Exception as e:
                    logger.warning(f"无法获取Ollama模型列表: {e}")
                    # 即使无法获取具体的本地模型，也要添加一个基础的Ollama代理项
                    agents.append({
                        "provider": provider,
                        "model": "unknown",  # 表示模型还未知
                        "agent_type": "react",
                        "supports_tools": True,
                        "recommended": False,
                        "description": "Ollama本地模型服务",
                    })
            else:
                # 对于其他提供商，使用预定义的模型列表
                for model_name, model_config in models.items():
                    # 确定Agent类型
                    if provider == "zhipu":
                        if model_name in ["glm-4.5", "glm-4.5-flash"]:
                            agent_type = "function_calling"
                        else:
                            agent_type = "react"
                    elif provider == "openai":
                        agent_type = "function_calling"
                    else:
                        agent_type = "react"

                    agents.append({
                        "provider": provider,
                        "model": model_name,
                        "agent_type": agent_type,
                        "supports_tools": model_config.get("supports_tools", False),
                        "recommended": model_config.get("recommended", False),
                        "description": model_config.get("description", ""),
                    })

        return agents


# 全局Agent管理器实例
agent_manager = AgentManager()


# 便捷函数
async def create_agent(provider: str, model: str = None, **kwargs):
    """
    创建Agent实例的便捷函数

    Args:
        provider: Provider名称
        model: 模型名称
        **kwargs: 其他参数

    Returns:
        Agent实例
    """
    return await agent_manager.create_agent(provider, model, **kwargs)


def get_available_agents() -> List[Dict[str, Any]]:
    """获取可用Agent列表的便捷函数"""
    return agent_manager.get_available_agents()
