"""
Zhipu AI Provider Implementation

智谱AI Provider实现，负责创建和管理智谱AI LLM实例。
"""

import logging
from typing import Dict, Any

from src.llm.langchain.providers.base import BaseProvider
from src.llm.langchain.instances.zhipu_llm import ZhipuAILLM

logger = logging.getLogger(__name__)


class ZhipuProvider(BaseProvider):
    """
    智谱AI Provider实现

    职责:
    - 创建智谱AI LLM实例
    - 验证API密钥格式
    - 管理智谱AI特定配置
    """

    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """
        创建智谱AI LLM实例

        Args:
            model: 模型名称 (glm-4-plus, glm-4.5, glm-4.5-flash等)
            api_key: 智谱AI API密钥
            **kwargs: 其他参数
                - temperature: 温度参数
                - max_tokens: 最大输出token数
                - streaming: 是否流式输出
                - thinking_mode: 思考模式(GLM-4.5特有)

        Returns:
            LangChain兼容的LLM实例

        Raises:
            ValueError: API密钥无效或模型不支持
        """
        if not api_key:
            raise ValueError("智谱AI API密钥不能为空")

        if not self.validate_api_key(api_key):
            logger.warning("智谱AI API密钥格式可能不正确")

        logger.info(f"创建智谱AI LLM: {model}")

        # 使用 ZhipuAILLM 包装器创建实例
        llm_wrapper = ZhipuAILLM(
            api_key=api_key,
            model=model,
            **kwargs
        )

        return llm_wrapper.create_llm()

    def validate_api_key(self, api_key: str) -> bool:
        """
        验证智谱AI API密钥格式

        智谱AI的API密钥通常是一个较长的字符串(>20字符)

        Args:
            api_key: API密钥

        Returns:
            是否有效
        """
        if not isinstance(api_key, str):
            return False

        # 基本长度检查
        if len(api_key) < 20:
            return False

        # 智谱AI密钥通常包含字母和数字
        return any(c.isalpha() for c in api_key) and any(c.isdigit() for c in api_key)

    def get_supported_models(self) -> Dict[str, Any]:
        """
        获取支持的智谱AI模型列表

        Returns:
            模型配置字典
        """
        return self.models

    def __repr__(self) -> str:
        return f"ZhipuProvider(name={self.name}, models={list(self.models.keys())})"
