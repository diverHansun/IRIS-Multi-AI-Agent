"""
Provider Registry

Provider注册表，负责从配置文件加载和管理所有Provider。
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

from src.config import config_loader

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM提供商枚举"""
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"


class ProviderRegistry:
    """
    Provider注册表

    职责:
    - 从配置文件加载Provider配置
    - 管理Provider实例
    - 提供Provider查询接口
    """

    def __init__(self):
        """初始化Provider注册表"""
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._load_from_config()

    def _load_from_config(self):
        """从配置文件加载Provider配置"""
        try:
            # 从JSON配置加载
            config_data = config_loader.load_config()
            self._providers = config_data.get("providers", {})

            logger.info(f"已加载 {len(self._providers)} 个Provider配置")

        except Exception as e:
            logger.error(f"加载Provider配置失败: {e}")
            self._providers = {}

    def reload_config(self):
        """重新加载配置"""
        logger.info("重新加载Provider配置...")
        try:
            config_data = config_loader.reload_config()
            self._providers = config_data.get("providers", {})
            logger.info("Provider配置重新加载完成")
            return True
        except Exception as e:
            logger.error(f"重新加载配置失败: {e}")
            return False

    def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        获取Provider配置

        Args:
            provider: Provider名称

        Returns:
            Provider配置，不存在返回None
        """
        provider_key = provider.upper()
        return self._providers.get(provider_key)

    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有Provider配置

        Returns:
            所有Provider配置
        """
        return self._providers.copy()

    def get_model_config(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """
        获取模型配置

        Args:
            provider: Provider名称
            model: 模型名称

        Returns:
            模型配置，不存在返回None
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None

        models = provider_config.get("models", {})
        return models.get(model)

    def get_model_info(self, provider: str, model: str = None) -> Dict[str, Any]:
        """
        获取模型详细信息（包含合并后的mode_defaults和mode_overrides）

        Args:
            provider: Provider名称
            model: 模型名称，None时使用默认模型

        Returns:
            模型信息
        """
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")

        # 确定模型
        if model is None:
            model = provider_config.get("default_model")

        model_config = self.get_model_config(provider, model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")

        # 合并mode_defaults和mode_overrides
        mode_defaults = provider_config.get("mode_defaults", {})
        mode_overrides = model_config.get("mode_overrides", {})

        # 合并llm模式
        llm_defaults = mode_defaults.get("llm", {})
        llm_overrides = mode_overrides.get("llm", {})
        llm_params = {**llm_defaults, **llm_overrides}

        # 合并agent模式
        agent_defaults = mode_defaults.get("agent", {})
        agent_overrides = mode_overrides.get("agent", {})
        agent_params = {**agent_defaults, **agent_overrides}

        # 构建返回信息
        return {
            "provider": provider.lower(),
            "provider_name": provider_config.get("name"),
            "model": model,
            "model_name": model_config.get("name", model),
            "name": model_config.get("name", model),
            "description": model_config.get("description", ""),
            "recommended": model_config.get("recommended", False),
            "model_features": model_config.get("model_features", []),
            "supports_tools": model_config.get("supports_tools", False),
            "max_tokens": model_config.get("max_tokens"),
            "context_window": model_config.get("context_window"),
            "mode_defaults": {
                "llm": llm_params,
                "agent": agent_params
            }
        }

    def validate_model(self, provider: str, model: str) -> bool:
        """
        验证模型是否受支持

        Args:
            provider: Provider名称
            model: 模型名称

        Returns:
            是否支持
        """
        model_config = self.get_model_config(provider, model)
        return model_config is not None

    def get_provider_instance(self, provider: str):
        """
        获取Provider实例（工厂方法）

        根据provider名称创建对应的Provider实例

        Args:
            provider: Provider名称 (zhipu, openai, ollama)

        Returns:
            Provider实例

        Raises:
            ValueError: Provider不存在或未实现
        """
        from src.llm.langchain.providers import (
            ZhipuProvider,
            OpenAIProvider,
            OllamaProvider,
        )

        # Provider类映射
        provider_classes = {
            "ZHIPU": ZhipuProvider,
            "OPENAI": OpenAIProvider,
            "OLLAMA": OllamaProvider,
        }

        provider_key = provider.upper()

        # 获取配置
        config = self.get_provider_config(provider)
        if not config:
            raise ValueError(f"Provider {provider} not found in configuration")

        # 获取Provider类
        provider_class = provider_classes.get(provider_key)
        if not provider_class:
            raise ValueError(f"No implementation found for provider: {provider}")

        # 创建并返回Provider实例
        logger.debug(f"Creating provider instance: {provider_class.__name__}")
        return provider_class(config)

    def __repr__(self) -> str:
        return f"ProviderRegistry(providers={list(self._providers.keys())})"


# 全局Provider注册表实例
provider_registry = ProviderRegistry()
