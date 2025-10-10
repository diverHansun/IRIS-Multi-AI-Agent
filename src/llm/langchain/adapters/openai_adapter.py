"""
OpenAI LLM Adapter

OpenAI的LLM适配器，处理特殊逻辑：
1. GPT-5系列: temperature_fixed=true，强制使用temperature=1.0
2. 从配置读取default_temperature
"""

import logging
from typing import Dict, Any

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMAdapter):
    """OpenAI LLM适配器"""

    def __init__(self, model: str, mode: str = "llm"):
        super().__init__(provider="OPENAI", model=model, mode=mode)

    def get_llm_params(self, **kwargs) -> Dict[str, Any]:
        """
        获取OpenAI LLM参数

        特殊逻辑处理:
        - GPT-5系列: temperature_fixed=true时，强制temperature=1.0
          用户传入的temperature会被忽略
        - 其他模型: 正常应用mode_defaults和mode_overrides

        Args:
            **kwargs: 用户传入的参数
                - temperature: 温度参数（GPT-5会被覆盖）
                - api_key: OpenAI API密钥
                - base_url: API基础URL
                等等

        Returns:
            处理后的LLM参数字典
        """
        # 获取基础参数（已包含mode_defaults + mode_overrides）
        params = self.get_base_params()

        # 特殊逻辑：temperature_fixed
        if self._model_config.get("temperature_fixed", False):
            # 从配置读取default_temperature
            fixed_temp = self._model_config.get("default_temperature", 1.0)
            params["temperature"] = fixed_temp

            # 警告：如果用户试图修改temperature
            if "temperature" in kwargs and kwargs["temperature"] != fixed_temp:
                logger.warning(
                    f"{self.model} 使用固定temperature={fixed_temp} "
                    f"(用户设置的{kwargs['temperature']}被忽略)"
                )

            # 从kwargs中移除temperature，避免覆盖
            user_params = {k: v for k, v in kwargs.items() if k != "temperature"}
        else:
            # 正常模型，允许用户覆盖temperature
            user_params = kwargs

        # 合并用户参数
        params = self.merge_user_params(params, user_params)

        logger.debug(f"OpenAI {self.model} ({self.mode}模式) 参数: {params}")

        return params

    def is_temperature_fixed(self) -> bool:
        """判断temperature是否固定"""
        return self._model_config.get("temperature_fixed", False)

    def get_default_temperature(self) -> float:
        """获取默认temperature"""
        return self._model_config.get("default_temperature", 0.1)
