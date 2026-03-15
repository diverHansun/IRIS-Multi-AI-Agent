"""
Zhipu AI LLM Adapter

Responsible for reading configuration and applying Zhipu-specific parameter logic.
"""

import logging
from typing import Any, Dict, Optional

from src.core.providers.llm_provider_registry import LLMProviderRegistry

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class ZhipuAdapter(LLMAdapter):
    """Zhipu AI LLM adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[LLMProviderRegistry] = None,
        mode: str = "llm",
        provider_name: str = "zhipu",
    ):
        super().__init__(
            provider=provider_name,
            model=model,
            provider_registry=provider_registry,
            mode=mode,
        )

    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        获取智谱AI LLM参数（只处理LLM参数）

        处理的LLM参数:
        - temperature: 温度参数
        - streaming: 流式输出
        - max_tokens: 最大token数
        - thinking_mode: 思考模式 (glm-4.5系列特有)

        不处理Agent参数:
        - max_iterations, max_execution_time等由AgentAdapter处理

        特殊逻辑:
        - glm-4.5/glm-4.5-flash: thinking_mode=True (从配置读取)
        - temperature从mode_overrides.llm优先应用

        Args:
            **kwargs: 用户传入的LLM参数

        Returns:
            处理后的LLM参数字典
        """
        params = self.get_base_params()

        if self.model in {"glm-4.5", "glm-4.5-flash"}:
            overrides = self.get_llm_mode_overrides()
            if "thinking_mode" in overrides:
                params["thinking_mode"] = overrides["thinking_mode"]
                logger.debug("%s using thinking_mode=%s", self.model, params["thinking_mode"])

        params = self.merge_user_params(params, kwargs)
        params.setdefault("model", self.model)

        logger.debug("Zhipu %s (%s) params: %s", self.model, self.mode, params)
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
