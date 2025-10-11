"""
Ollama LLM Adapter

Ollama本地模型的LLM适配器，处理特殊逻辑：
1. Agent模式: 温度优化（默认0.0而不是0.1）
2. 自动模型选择（"auto"）
3. disable_thinking_mode默认为True
"""

import logging
from typing import Dict, Any

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):
    """Ollama LLM适配器"""

    def __init__(self, model: str, mode: str = "llm"):
        super().__init__(provider="OLLAMA", model=model, mode=mode)

    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        获取Ollama LLM参数

        特殊逻辑处理:
        - Agent模式: 如果temperature为默认0.1，自动降为0.0优化性能
        - disable_thinking_mode: 默认True（除非用户明确设置）
        - base_url: 从kwargs或配置读取

        Args:
            **kwargs: 用户传入的参数
                - temperature: 温度参数（Agent模式会优化）
                - base_url: Ollama服务地址
                - disable_thinking_mode: 是否禁用思考模式
                等等

        Returns:
            处理后的LLM参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = self.get_base_params()

        # 特殊逻辑1: Agent模式温度优化
        if self.mode == "agent":
            # 如果用户没有显式指定temperature，或者使用默认值0.1
            user_temp = kwargs.get("temperature")

            # 如果是默认温度（0.1），降为0.0以优化Agent性能
            if user_temp is None or user_temp == 0.1:
                params["temperature"] = 0.0
                logger.debug(f"Ollama Agent模式温度优化: temperature=0.0")
            else:
                # 用户显式指定了非默认值，使用用户的设置
                params["temperature"] = user_temp

        # 特殊逻辑2: disable_thinking_mode默认为True
        if "disable_thinking_mode" not in kwargs:
            params["disable_thinking_mode"] = True

        # 合并用户参数（排除已处理的temperature）
        user_params = kwargs.copy()
        if self.mode == "agent" and "temperature" in user_params:
            # temperature已经在上面处理过了
            user_params.pop("temperature")

        params = self.merge_user_params(params, user_params)

        logger.debug(f"Ollama {self.model} ({self.mode}模式) 参数: {params}")

        return params

    async def resolve_auto_model(self, base_url: str) -> str:
        """
        解析"auto"模型，选择本地第一个可用模型

        Args:
            base_url: Ollama服务地址

        Returns:
            实际的模型名称
        """
        if self.model != "auto":
            return self.model

        try:
            # 动态导入避免循环依赖
            from src.llm.langchain.providers.ollama import list_ollama_models

            local_models = await list_ollama_models(base_url, timeout=5)

            if local_models:
                selected_model = local_models[0]
                logger.info(f"自动选择Ollama模型: {selected_model}")
                return selected_model
            else:
                # 回退到默认模型
                default_model = "gpt-oss:20b"
                logger.warning(f"未找到本地Ollama模型，使用默认: {default_model}")
                return default_model

        except Exception as e:
            # 出错时回退到默认模型
            default_model = "gpt-oss:20b"
            logger.warning(f"获取Ollama模型列表失败，使用默认: {default_model}, 错误: {e}")
            return default_model
