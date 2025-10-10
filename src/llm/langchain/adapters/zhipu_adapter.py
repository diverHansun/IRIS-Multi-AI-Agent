"""
Zhipu AI LLM Adapter

智谱AI的LLM适配器，处理特殊逻辑：
1. glm-4.5/glm-4.5-flash: 启用thinking_mode
2. 从配置读取temperature覆盖
"""

import logging
from typing import Dict, Any

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class ZhipuAdapter(LLMAdapter):
    """智谱AI LLM适配器"""

    def __init__(self, model: str, mode: str = "llm"):
        super().__init__(provider="ZHIPU", model=model, mode=mode)

    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        获取智谱AI LLM参数

        特殊逻辑处理:
        - glm-4.5/glm-4.5-flash: thinking_mode=True (从配置读取)
        - temperature从mode_overrides优先应用

        Args:
            **kwargs: 用户传入的参数
                - temperature: 温度参数
                - streaming: 流式输出
                - max_tokens: 最大token数
                等等

        Returns:
            处理后的LLM参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = self.get_base_params()

        # 特殊逻辑：thinking_mode
        # glm-4.5和glm-4.5-flash在配置中已设置thinking_mode: true
        # 这里只需要确保它被正确读取
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            # 从mode_overrides中读取thinking_mode
            overrides = self.get_mode_overrides()
            if "thinking_mode" in overrides:
                params["thinking_mode"] = overrides["thinking_mode"]
                logger.debug(f"{self.model} 使用thinking_mode={params['thinking_mode']}")

        # 合并用户参数
        params = self.merge_user_params(params, kwargs)

        logger.debug(f"智谱AI {self.model} ({self.mode}模式) 参数: {params}")

        return params

    def supports_function_calling(self) -> bool:
        """判断模型是否支持Function Calling"""
        # glm-4.5和glm-4.5-flash使用原生Function Calling
        return self.model in ["glm-4.5", "glm-4.5-flash"]

    def get_agent_type(self) -> str:
        """
        获取推荐的Agent类型

        Returns:
            "function_calling" 或 "react"
        """
        if self.supports_function_calling():
            return "function_calling"
        return "react"
