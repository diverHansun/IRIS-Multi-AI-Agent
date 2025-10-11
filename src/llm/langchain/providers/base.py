"""
Provider Base Class

Provider抽象基类，定义统一的Provider接口。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    Provider抽象基类

    职责:
    - 定义统一的Provider接口
    - 封装Provider特定的创建逻辑
    - 管理Provider的配置信息
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化Provider

        Args:
            config: Provider配置，来自providers.json
        """
        self.config = config
        self.name = config.get("name")
        self.default_model = config.get("default_model")
        self.api_key_env = config.get("api_key_env")
        self.models = config.get("models", {})
        self.mode_defaults = config.get("mode_defaults", {})

        logger.debug(f"Provider初始化: {self.name}")

    @abstractmethod
    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """
        创建LLM实例（必须由子类实现）

        Args:
            model: 模型名称
            api_key: API密钥
            **kwargs: 其他参数

        Returns:
            LLM实例
        """
        pass

    @abstractmethod
    def validate_api_key(self, api_key: str) -> bool:
        """
        验证API密钥格式（必须由子类实现）

        Args:
            api_key: API密钥

        Returns:
            是否有效
        """
        pass

    def get_supported_models(self) -> Dict[str, Any]:
        """
        获取支持的模型列表

        Returns:
            模型配置字典
        """
        return self.models

    def get_default_model(self) -> str:
        """获取默认模型"""
        return self.default_model

    def get_model_config(self, model: str) -> Optional[Dict[str, Any]]:
        """
        获取模型配置

        Args:
            model: 模型名称

        Returns:
            模型配置，不存在返回None
        """
        return self.models.get(model)

    def validate_model(self, model: str) -> bool:
        """
        验证模型是否支持

        Args:
            model: 模型名称

        Returns:
            是否支持
        """
        return model in self.models

    def get_mode_defaults(self, mode: str) -> Dict[str, Any]:
        """
        获取模式默认参数

        Args:
            mode: 模式名称 ("llm" 或 "agent")

        Returns:
            模式默认参数
        """
        return self.mode_defaults.get(mode, {})

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, default_model={self.default_model})"
