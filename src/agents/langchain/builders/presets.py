"""
Agent Builder Presets

预设配置，简化常见Agent构建场景。
"""

import logging
from typing import Optional

from .agent_builder import AgentBuilder

logger = logging.getLogger(__name__)


class AgentPresets:
    """Agent预设配置集合"""

    @staticmethod
    def for_react(
        provider: str = "zhipu",
        model: str = "glm-4-plus",
        temperature: float = 0.1,
        enable_memory: bool = True
    ) -> AgentBuilder:
        """
        ReAct Agent预设

        适用场景：需要推理和行动的复杂任务

        Args:
            provider: 提供商（默认zhipu）
            model: 模型（默认glm-4-plus）
            temperature: 温度（默认0.1，精确推理）
            enable_memory: 是否启用记忆

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider(provider)
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        logger.debug(f"创建ReAct预设: {provider}/{model}")
        return builder

    @staticmethod
    def for_function_calling(
        model: str = "glm-4.5-flash",
        temperature: float = 0.1,
        enable_memory: bool = True
    ) -> AgentBuilder:
        """
        Function Calling Agent预设

        适用场景：需要高效工具调用的任务
        目前仅支持智谱AI的glm-4.5系列

        Args:
            model: 模型（默认glm-4.5-flash）
            temperature: 温度（默认0.1）
            enable_memory: 是否启用记忆

        Returns:
            配置好的AgentBuilder
        """
        if model not in ["glm-4.5", "glm-4.5-flash"]:
            logger.warning(f"模型{model}可能不支持Function Calling，推荐使用glm-4.5或glm-4.5-flash")

        builder = AgentBuilder()
        builder.with_provider("zhipu")
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        logger.debug(f"创建Function Calling预设: {model}")
        return builder

    @staticmethod
    def for_chat(
        provider: str = "zhipu",
        model: str = "glm-4-plus",
        temperature: float = 0.7,
        enable_memory: bool = True
    ) -> AgentBuilder:
        """
        聊天Agent预设

        适用场景：自然对话、创意生成

        Args:
            provider: 提供商（默认zhipu）
            model: 模型（默认glm-4-plus）
            temperature: 温度（默认0.7，较高创造性）
            enable_memory: 是否启用记忆

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider(provider)
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        logger.debug(f"创建Chat预设: {provider}/{model}")
        return builder

    @staticmethod
    def for_coding(
        provider: str = "zhipu",
        model: str = "glm-4.5",
        temperature: float = 0.1,
        enable_memory: bool = True
    ) -> AgentBuilder:
        """
        代码生成Agent预设

        适用场景：代码生成、调试、重构

        Args:
            provider: 提供商（默认zhipu）
            model: 模型（默认glm-4.5，代码能力强）
            temperature: 温度（默认0.1，精确生成）
            enable_memory: 是否启用记忆

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider(provider)
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        logger.debug(f"创建Coding预设: {provider}/{model}")
        return builder

    @staticmethod
    def for_ollama_local(
        model: str = "auto",
        temperature: float = 0.0,
        enable_memory: bool = True,
        base_url: Optional[str] = None
    ) -> AgentBuilder:
        """
        Ollama本地模型预设

        适用场景：本地部署、离线使用

        Args:
            model: 模型（默认auto，自动选择）
            temperature: 温度（默认0.0，Agent模式优化）
            enable_memory: 是否启用记忆
            base_url: Ollama服务地址

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider("ollama")
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        if base_url:
            builder.with_base_url(base_url)

        # Ollama特殊优化
        builder.with_extra_params(disable_thinking_mode=True)

        logger.debug(f"创建Ollama本地预设: {model}")
        return builder

    @staticmethod
    def for_gpt5(
        model: str = "gpt-5",
        enable_memory: bool = True,
        api_key: Optional[str] = None
    ) -> AgentBuilder:
        """
        GPT-5预设

        适用场景：高级推理、复杂任务
        注意：temperature固定为1.0，由适配器自动处理

        Args:
            model: 模型（默认gpt-5）
            enable_memory: 是否启用记忆
            api_key: OpenAI API密钥

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider("openai")
        builder.with_model(model)
        # 不设置temperature，让OpenAIAdapter自动使用固定值1.0
        builder.with_memory(enabled=enable_memory)

        if api_key:
            builder.with_api_key(api_key)

        logger.debug(f"创建GPT-5预设: {model} (temperature自动设为1.0)")
        return builder

    @staticmethod
    def for_langgraph(
        provider: str = "zhipu",
        model: str = "glm-4.5",
        temperature: float = 0.1,
        enable_memory: bool = True
    ) -> AgentBuilder:
        """
        LangGraph工作流预设

        适用场景：复杂工作流、多步骤任务（未来集成）

        Args:
            provider: 提供商（默认zhipu）
            model: 模型（默认glm-4.5）
            temperature: 温度（默认0.1）
            enable_memory: 是否启用记忆

        Returns:
            配置好的AgentBuilder
        """
        builder = AgentBuilder()
        builder.with_provider(provider)
        builder.with_model(model)
        builder.with_temperature(temperature)
        builder.with_memory(enabled=enable_memory)

        logger.debug(f"创建LangGraph预设: {provider}/{model} (未来将集成工作流功能)")
        return builder
