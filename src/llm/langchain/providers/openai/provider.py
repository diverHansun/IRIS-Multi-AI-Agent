"""
OpenAI Provider Implementation

OpenAI Provider实现，负责创建和管理OpenAI LLM实例。
"""

import logging
from typing import Dict, Any

from src.core.langchain.providers import BaseProvider
from src.llm.langchain.managers import llm_manager
from src.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """
    OpenAI Provider实现

    职责:
    - 创建OpenAI LLM实例
    - 验证API密钥格式
    - 管理OpenAI特定配置
    """

    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """
        创建OpenAI LLM实例

        Args:
            model: 模型名称 (gpt-4o, gpt-4o-mini等)
            api_key: OpenAI API密钥
            **kwargs: 其他参数
                - base_url: 自定义API端点URL
                - temperature: 温度参数
                - max_tokens: 最大输出token数
                - streaming: 是否流式输出

        Returns:
            LangChain兼容的LLM实例

        Raises:
            ValueError: API密钥无效或模型不支持
        """
        if not api_key:
            raise ValueError("OpenAI API密钥不能为空")

        if not self.validate_api_key(api_key):
            logger.warning("OpenAI API密钥格式可能不正确")

        logger.info(f"创建OpenAI LLM: {model}")

        # 直接使用llm_manager创建实例
        # 设置API密钥
        llm_manager.set_api_key(self.name.lower(), api_key)
        
        # 检查是否有自定义base_url (从配置或kwargs)
        base_url = kwargs.pop('base_url', None)
        if not base_url:
            base_url = settings.openai_base_url if hasattr(settings, 'openai_base_url') else None

        # 将base_url添加到kwargs中
        if base_url:
            kwargs['base_url'] = base_url

        # 使用llm_manager创建LLM实例
        return llm_manager.create_llm(
            provider=self.name.lower(),
            model=model,
            **kwargs
        )

    def validate_api_key(self, api_key: str) -> bool:
        """
        验证OpenAI API密钥格式

        OpenAI API密钥通常以 'sk-' 或 'sk-proj-' 开头

        Args:
            api_key: API密钥

        Returns:
            是否有效
        """
        if not isinstance(api_key, str):
            return False

        # OpenAI密钥以 'sk-' 开头
        if not api_key.startswith('sk-'):
            return False

        # 基本长度检查 (OpenAI密钥通常较长)
        if len(api_key) < 20:
            return False

        return True

    def get_supported_models(self) -> Dict[str, Any]:
        """
        获取支持的OpenAI模型列表

        Returns:
            模型配置字典
        """
        return self.models

    def __repr__(self) -> str:
        return f"OpenAIProvider(name={self.name}, models={list(self.models.keys())})"