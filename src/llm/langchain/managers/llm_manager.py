"""
LLM Manager - 统一LLM管理接口

提供统一的LLM选择、创建和管理功能
支持多个LLM提供商（智谱AI、OpenAI等）

职责:
- API密钥管理
- 委托ProviderRegistry进行配置管理
- 委托Provider实现进行LLM创建
- 提供向后兼容的查询接口
"""

import logging
from typing import Dict, Any, List, Union
from enum import Enum

from src.config import settings
from src.core.langchain.providers import provider_registry

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """LLM提供商枚举"""
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"

class LLMManager:
    """
    LLM管理器 (简化版)

    职责:
    - API密钥管理
    - 委托ProviderRegistry进行配置查询
    - 委托Provider实现进行LLM创建
    """

    def __init__(self):
        """初始化LLM管理器"""
        self.provider_registry = provider_registry  # 委托配置管理
        self._api_keys = {}
        self._load_api_keys()
        logger.info("LLM Manager initialized")

    def _load_api_keys(self):
        """从配置中加载API密钥"""
        try:
            # 智谱AI API密钥
            if settings.zhipu_api_key:
                self._api_keys[LLMProvider.ZHIPU] = settings.zhipu_api_key

            # OpenAI API密钥
            if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
                self._api_keys[LLMProvider.OPENAI] = settings.openai_api_key

            logger.info(f"已加载 {len(self._api_keys)} 个LLM提供商的API密钥")

        except Exception as e:
            logger.warning(f"加载API密钥时出错: {str(e)}")

    def reload_config(self):
        """重新加载配置 (委托给ProviderRegistry)"""
        logger.info("🔄 重新加载LLM配置...")
        return self.provider_registry.reload_config()

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """获取可用的LLM提供商列表"""
        providers: List[Dict[str, Any]] = []

        # 从ProviderRegistry获取所有Provider配置
        all_providers = self.provider_registry.list_providers()

        for provider_key, config in all_providers.items():
            provider_name = provider_key.lower()

            # 检查是否有API密钥 (Ollama不需要)
            has_api_key = (provider_name == "ollama") or (
                LLMProvider(provider_name) in self._api_keys
            )

            # 获取Provider实例以访问模型列表
            try:
                provider_instance = self.provider_registry.get_provider_instance(provider_key)
                models_registry = provider_instance.get_supported_models()
            except Exception as e:
                logger.warning(f"无法获取 {provider_key} 的模型列表: {e}")
                models_registry = config.get("models", {})

            provider_info = {
                "provider": provider_name,
                "name": config.get("name", provider_key),
                "available": has_api_key,
                "default_model": config.get("default_model"),
                "models": list(models_registry.keys()),
                "api_key_required": config.get("api_key_env"),
                "mode_defaults": dict(config.get("mode_defaults", {}))
            }

            # 获取模型详细信息
            models_detail: Dict[str, Any] = {}
            for model_name in models_registry:
                try:
                    models_detail[model_name] = self.get_llm_info(provider_name, model_name)
                except Exception as e:
                    logger.debug(f"获取模型 {model_name} 详细信息失败: {e}")
                    model_cfg = models_registry.get(model_name, {})
                    models_detail[model_name] = {
                        "model": model_name,
                        "name": model_cfg.get("name", model_name),
                        "description": model_cfg.get("description", "")
                    }

            if models_detail:
                provider_info["models_detail"] = models_detail

            providers.append(provider_info)

        return providers

    def get_provider_models(self, provider: Union[str, LLMProvider]) -> Dict[str, Any]:
        """获取指定提供商的模型注册信息 (委托给ProviderRegistry)"""
        if isinstance(provider, str):
            provider_name = provider
        else:
            provider_name = provider.value

        # 获取Provider配置
        config = self.provider_registry.get_provider_config(provider_name.upper())
        if not config:
            raise ValueError(f"不支持的LLM提供商: {provider_name}")

        # 获取Provider实例以访问模型
        try:
            provider_instance = self.provider_registry.get_provider_instance(provider_name.upper())
            models_registry = provider_instance.get_supported_models()
        except Exception as e:
            logger.warning(f"无法获取 {provider_name} 的模型列表: {e}")
            models_registry = config.get("models", {})

        # 检查是否可用
        available = (provider_name.lower() == "ollama") or (
            LLMProvider(provider_name.lower()) in self._api_keys
        )

        return {
            "provider": provider_name.lower(),
            "name": config.get("name"),
            "models": models_registry,
            "default_model": config.get("default_model"),
            "available": available,
            "mode_defaults": dict(config.get("mode_defaults", {}))
        }

    def validate_model(self, provider: Union[str, LLMProvider], model: str) -> bool:
        """验证模型是否受支持 (委托给ProviderRegistry)"""
        if isinstance(provider, str):
            provider_name = provider
        else:
            provider_name = provider.value

        return self.provider_registry.validate_model(provider_name, model)

    def create_llm(
        self,
        provider: Union[str, LLMProvider],
        model: str = None,
        api_key: str = None,
        **kwargs
    ):
        """
        创建LLM实例 (委托给Provider)

        Args:
            provider: LLM提供商
            model: 模型名称，为None时使用默认模型
            api_key: API密钥，为None时使用配置中的密钥
            **kwargs: 其他参数

        Returns:
            LLM实例
        """
        if isinstance(provider, str):
            provider_enum = LLMProvider(provider.lower())
            provider_name = provider.lower()
        else:
            provider_enum = provider
            provider_name = provider.value

        # 获取Provider实例
        try:
            provider_instance = self.provider_registry.get_provider_instance(provider_name.upper())
        except ValueError as e:
            raise ValueError(f"不支持的LLM提供商: {provider_name}") from e

        # 确定模型
        if not model:
            model = provider_instance.get_default_model()

        # 确定API密钥（Ollama不需要）
        if provider_name != "ollama":
            if not api_key:
                api_key = self._api_keys.get(provider_enum)
                if not api_key:
                    config = self.provider_registry.get_provider_config(provider_name.upper())
                    api_key_env = config.get("api_key_env", "API_KEY")
                    raise ValueError(f"未找到 {provider_name} 的API密钥，请设置环境变量 {api_key_env}")

        # 验证模型
        if not provider_instance.validate_model(model):
            logger.warning(f"模型 {model} 可能不受 {provider_name} 支持")

        # 委托Provider创建LLM实例
        logger.info(f"创建LLM: {provider_name}/{model}")
        return provider_instance.create_llm(model, api_key, **kwargs)

    def get_llm_info(self, provider: Union[str, LLMProvider], model: str = None) -> Dict[str, Any]:
        """获取LLM信息 (委托给ProviderRegistry)"""
        if isinstance(provider, str):
            provider_name = provider
        else:
            provider_name = provider.value

        # 委托给ProviderRegistry
        model_info = self.provider_registry.get_model_info(provider_name, model)

        # 添加可用性信息
        provider_enum_value = provider_name.lower()
        available = (provider_enum_value == "ollama") or (
            LLMProvider(provider_enum_value) in self._api_keys
        )
        model_info["available"] = available

        return model_info

    def set_api_key(self, provider: Union[str, LLMProvider], api_key: str):
        """设置API密钥"""
        if isinstance(provider, str):
            provider_enum = LLMProvider(provider.lower())
            provider_name = provider.lower()
        else:
            provider_enum = provider
            provider_name = provider.value

        # 获取Provider实例进行验证
        try:
            provider_instance = self.provider_registry.get_provider_instance(provider_name.upper())

            if not provider_instance.validate_api_key(api_key):
                logger.warning(f"{provider_name} API密钥格式可能不正确")

            self._api_keys[provider_enum] = api_key
            logger.info(f"已设置 {provider_name} 的API密钥")

        except ValueError as e:
            raise ValueError(f"不支持的LLM提供商: {provider_name}") from e

    def get_recommended_models(self) -> List[Dict[str, Any]]:
        """获取推荐模型列表"""
        recommended: List[Dict[str, Any]] = []

        # 遍历所有可用的Provider
        all_providers = self.provider_registry.list_providers()

        for provider_key, config in all_providers.items():
            provider_name = provider_key.lower()

            # 检查Provider是否可用
            provider_available = (provider_name == "ollama") or (
                LLMProvider(provider_name) in self._api_keys
            )

            if not provider_available:
                continue

            # 获取模型列表
            try:
                provider_instance = self.provider_registry.get_provider_instance(provider_key)
                models_registry = provider_instance.get_supported_models()
            except:
                models_registry = config.get("models", {})

            # 查找推荐模型
            for model_name in models_registry:
                try:
                    info = self.get_llm_info(provider_name, model_name)
                    if info.get("recommended"):
                        recommended.append({
                            "provider": info["provider"],
                            "provider_name": info["provider_name"],
                            "model": info["model"],
                            "model_name": info["model_name"],
                            "description": info["description"]
                        })
                except Exception as e:
                    logger.debug(f"获取模型 {model_name} 信息失败: {e}")
                    continue

        return recommended


# 全局LLM管理器实例
llm_manager = LLMManager()


# 便捷函数
def get_available_providers() -> List[Dict[str, Any]]:
    """获取可用的LLM提供商"""
    return llm_manager.get_available_providers()


def create_llm(provider: str, model: str = None, **kwargs):
    """创建LLM实例的便捷函数"""
    return llm_manager.create_llm(provider, model, **kwargs)


def get_llm_info(provider: str, model: str = None) -> Dict[str, Any]:
    """获取LLM信息的便捷函数"""
    return llm_manager.get_llm_info(provider, model)


def get_recommended_models() -> List[Dict[str, Any]]:
    """获取推荐模型"""
    return llm_manager.get_recommended_models()


def reload_llm_config() -> bool:
    """重新加载LLM配置的便捷函数"""
    return llm_manager.reload_config()
