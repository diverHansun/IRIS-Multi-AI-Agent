"""
Ollama Agent Factory

Ollama本地模型Agent工厂，统一创建Ollama Agent。
"""

import logging
from typing import Dict, Any, Optional

from .base import BaseAgentFactory

logger = logging.getLogger(__name__)


class OllamaAgentFactory(BaseAgentFactory):
    """Ollama Agent工厂"""

    def __init__(self):
        super().__init__(provider="OLLAMA")

    async def create_agent(
        self,
        model: str,
        verbose: bool = False,
        temperature: Optional[float] = None,
        enable_memory: bool = True,
        global_memory_manager = None,
        base_url: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        创建Ollama Agent

        特殊逻辑：
        - 如果model为"auto"，自动选择本地第一个可用模型
        - Agent模式默认temperature=0.0优化
        - disable_thinking_mode默认为True

        Args:
            model: 模型名称（可以是"auto"）
            verbose: 是否详细输出
            temperature: 温度参数
            enable_memory: 是否启用记忆
            global_memory_manager: 全局记忆管理器
            base_url: Ollama服务地址
            **kwargs: 其他参数

        Returns:
            OllamaAgent实例
        """
        from src.agents.langchain.instances.ollama_agent import build_ollama_agent
        from src.config import settings

        # 处理base_url
        if base_url is None:
            base_url = settings.ollama_base_url

        # 处理auto模型选择
        actual_model = model
        if model == "auto":
            try:
                from src.core.langchain.providers.utils import list_ollama_models
                local_models = await list_ollama_models(base_url, timeout=5)

                if local_models:
                    actual_model = local_models[0]
                    logger.info(f"自动选择Ollama模型: {actual_model}")
                else:
                    actual_model = "gpt-oss:20b"
                    logger.warning(f"未找到本地Ollama模型，使用默认: {actual_model}")

            except Exception as e:
                actual_model = "gpt-oss:20b"
                logger.warning(f"获取Ollama模型列表失败，使用默认: {actual_model}, 错误: {e}")

        logger.info(f"创建Ollama Agent: {actual_model}")

        # Agent模式温度优化
        agent_temperature = temperature
        if temperature is None or temperature == 0.1:
            agent_temperature = 0.0
            logger.debug("Ollama Agent模式温度优化: temperature=0.0")

        agent = await build_ollama_agent(
            model=actual_model,
            base_url=base_url,
            verbose=verbose,
            temperature=agent_temperature,
            enable_memory=enable_memory,
            global_memory_manager=global_memory_manager,
            disable_thinking_mode=kwargs.get('disable_thinking_mode', True),
            **{k: v for k, v in kwargs.items() if k != 'disable_thinking_mode'}
        )

        logger.info(f"成功创建Ollama Agent: {actual_model}")
        return agent
