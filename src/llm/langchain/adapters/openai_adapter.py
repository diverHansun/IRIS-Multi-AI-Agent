"""
OpenAI LLM Adapter.
"""

import logging
from typing import Any, Dict, Optional

from src.core.langchain.providers.provider_registry import ProviderRegistry

from .base import LLMAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMAdapter):
    """OpenAI LLM adapter."""

    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[ProviderRegistry] = None,
        mode: str = "llm",
    ):
        super().__init__(
            provider="OPENAI",
            model=model,
            provider_registry=provider_registry,
            mode=mode,
        )

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
        params = self.get_base_params()

        if self._model_config.get("temperature_fixed", False):
            fixed_temp = self._model_config.get("default_temperature", 1.0)
            params["temperature"] = fixed_temp

            if "temperature" in kwargs and kwargs["temperature"] != fixed_temp:
                logger.warning(
                    "%s enforces temperature=%s (user input %s ignored)",
                    self.model,
                    fixed_temp,
                    kwargs["temperature"],
                )

            user_params = {k: v for k, v in kwargs.items() if k != "temperature"}
        else:
            user_params = kwargs

        params = self.merge_user_params(params, user_params)
        params.setdefault("model", self.model)

        logger.debug("OpenAI %s (%s) params: %s", self.model, self.mode, params)
        return params

    def is_temperature_fixed(self) -> bool:
        """判断temperature是否固定"""
        return self._model_config.get("temperature_fixed", False)

    def get_default_temperature(self) -> float:
        """获取默认temperature"""
        return self._model_config.get("default_temperature", 0.1)
