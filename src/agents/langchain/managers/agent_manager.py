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
        # 延迟导入避免循环依赖
        from src.llm.langchain.managers import llm_manager
        self.llm_manager = llm_manager

        logger.info("AgentManager initialized")

    def create_agent(
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

        # 4. 确定Agent类并创建实例
        agent_class = self._get_agent_class(provider, model, agent_type)

        agent = agent_class(
            provider=provider,
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
            # 从LLM Manager获取Provider配置
            providers = self.llm_manager.get_available_providers()
            for p in providers:
                if p["provider"].upper() == provider:
                    return p

            raise ValueError(f"Provider {provider} not found")
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

        # LLM Adapter使用"llm"模式
        return adapter_class(model=model, mode="llm")

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

        return adapter_class(provider=provider, model=model)

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

        providers = self.llm_manager.get_available_providers()
        for provider_info in providers:
            if not provider_info.get("available"):
                continue

            provider = provider_info["provider"]
            for model_name in provider_info.get("models", []):
                model_info = provider_info.get("models_detail", {}).get(model_name, {})

                # 确定Agent类型
                if provider.upper() == "ZHIPU":
                    if model_name in ["glm-4.5", "glm-4.5-flash"]:
                        agent_type = "function_calling"
                    else:
                        agent_type = "react"
                elif provider.upper() == "OPENAI":
                    agent_type = "function_calling"
                else:
                    agent_type = "react"

                agents.append({
                    "provider": provider,
                    "model": model_name,
                    "agent_type": agent_type,
                    "supports_tools": model_info.get("supports_tools", False),
                    "recommended": model_info.get("recommended", False),
                    "description": model_info.get("description", ""),
                })

        return agents


# 全局Agent管理器实例
agent_manager = AgentManager()


# 便捷函数
def create_agent(provider: str, model: str = None, **kwargs):
    """
    创建Agent实例的便捷函数

    Args:
        provider: Provider名称
        model: 模型名称
        **kwargs: 其他参数

    Returns:
        Agent实例
    """
    return agent_manager.create_agent(provider, model, **kwargs)


def get_available_agents() -> List[Dict[str, Any]]:
    """获取可用Agent列表的便捷函数"""
    return agent_manager.get_available_agents()
