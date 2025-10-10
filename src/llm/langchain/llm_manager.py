"""
LLM Manager - 统一LLM管理接口

提供统一的LLM选择、创建和管理功能
支持多个LLM提供商（智谱AI、OpenAI等）
"""

import logging
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from .instances.zhipu_llm import ZhipuAILLM
from .instances.openai_llm import OpenAILLM, build_openai_chat
from ...config import settings, config_loader

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """LLM提供商枚举"""
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"

class LLMManager:
    """LLM管理器"""
    
    # 硬编码的备用配置（当JSON文件加载失败时使用）
    FALLBACK_LLMS = {
        LLMProvider.ZHIPU: {
            "name": "智谱AI",
            "default_model": "glm-4.5",
            "mode_defaults": {
                "llm": {
                    "temperature": 0.1,
                    "streaming": True
                },
                "agent": {
                    "temperature": 0.1,
                    "memory_enabled": True,
                    "max_iterations": 8,
                    "max_execution_time": 300,
                    "streaming": False
                }
            },
            "models": {
                "glm-4-plus": {
                    "name": "GLM-4-Plus",
                    "description": "智谱AI最新旗舰模型，综合能力强",
                    "recommended": True,
                    "model_features": ["通用对话", "推理分析", "工具调用", "成本优化"],
                    "supports_tools": True
                },
                "glm-4.5": {
                    "name": "GLM-4.5",
                    "description": "智谱AI新一代MoE架构模型，支持128K上下文，专精代码推理和工具调用",
                    "recommended": True,
                    "model_features": ["深度思考模式", "128K长上下文", "代码生成专精", "工具调用优化", "复杂推理增强"],
                    "supports_tools": True,
                    "mode_overrides": {
                        "llm": {
                            "thinking_mode": True
                        },
                        "agent": {
                            "max_iterations": 15,
                            "max_execution_time": 180
                        }
                    }
                }
            }
        },
        LLMProvider.OPENAI: {
            "name": "OpenAI",
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "class": OpenAILLM,
            "mode_defaults": {
                "llm": {
                    "temperature": 0.1,
                    "streaming": True
                },
                "agent": {
                    "temperature": 0.1,
                    "memory_enabled": True,
                    "max_iterations": 10,
                    "max_execution_time": 300,
                    "streaming": False
                }
            },
            "models": {
                "gpt-4o-mini": {
                    "name": "GPT-4o-mini",
                    "description": "轻量级GPT-4o版本，速度快成本低",
                    "recommended": True,
                    "model_features": ["多模态", "长上下文", "快速推理", "成本优化"],
                    "supports_tools": True
                }
            }
        },
        LLMProvider.OLLAMA: {
            "name": "Ollama本地模型",
            "default_model": "auto",
            "api_key_env": None,
            "class": None,
            "mode_defaults": {
                "llm": {
                    "temperature": 0.1,
                    "streaming": True
                },
                "agent": {
                    "temperature": 0.0,
                    "memory_enabled": True,
                    "max_iterations": 3,
                    "max_execution_time": 30,
                    "streaming": False
                }
            },
            "models": {}
        }
    }

    @staticmethod
    def _merge_mode_defaults(base_defaults: Optional[Dict[str, Dict[str, Any]]],
                             overrides: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """合并模式默认参数和覆盖参数"""
        merged: Dict[str, Dict[str, Any]] = {}
        if base_defaults:
            for mode, params in base_defaults.items():
                merged[mode] = dict(params)
        if overrides:
            for mode, params in overrides.items():
                target = merged.setdefault(mode, {})
                target.update(params)
        return merged

    def _get_provider_models(self, provider: LLMProvider, config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """获取提供商支持的模型列表"""
        models = dict(config.get("models", {}))
        if provider == LLMProvider.OLLAMA:
            try:
                from .instances.ollama_llm import OllamaLLM  # 动态导入避免循环依赖
                # 使用动态检测方法获取本地已安装的模型
                dynamic_models = OllamaLLM.get_supported_models()
                models.update(dynamic_models)
            except Exception as e:
                logger.warning(f"获取Ollama动态模型失败: {e}")
                pass
        return models


    def __init__(self):
        """初始化LLM管理器"""
        self._api_keys = {}
        self._load_api_keys()
        self._load_config()
    
    def _load_config(self):
        """加载LLM配置"""
        try:
            # 尝试从JSON文件加载配置
            config_data = config_loader.load_config()
            self.SUPPORTED_LLMS = self._convert_json_config(config_data)
            logger.info("✅ 已从JSON配置文件加载LLM配置")
        except Exception as e:
            # 降级到硬编码配置
            logger.warning(f"⚠️ 从JSON加载配置失败，使用备用配置: {e}")
            self.SUPPORTED_LLMS = self.FALLBACK_LLMS.copy()

    def _convert_json_config(self, config_data: Dict[str, Any]) -> Dict[LLMProvider, Dict[str, Any]]:
        """将JSON配置转换为内部格式"""
        converted = {}
        
        for provider_key, provider_config in config_data["providers"].items():
            try:
                # 转换provider key为枚举
                provider_enum = LLMProvider(provider_key.lower())
                
                # 复制配置并添加类引用（如果需要）
                config_copy = dict(provider_config)
                
                # 添加类引用
                if provider_enum == LLMProvider.ZHIPU:
                    config_copy["api_key_env"] = "ZHIPU_API_KEY"
                    config_copy["class"] = ZhipuAILLM
                elif provider_enum == LLMProvider.OPENAI:
                    if "class" in config_copy and config_copy["class"] == "OpenAILLM":
                        config_copy["class"] = OpenAILLM
                
                converted[provider_enum] = config_copy
                
            except ValueError as e:
                logger.warning(f"跳过不支持的provider: {provider_key}, 错误: {e}")
                continue
        
        return converted
    
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
        """重新加载配置"""
        logger.info("🔄 重新加载LLM配置...")
        try:
            # 重新加载JSON配置
            config_data = config_loader.reload_config()
            self.SUPPORTED_LLMS = self._convert_json_config(config_data)
            logger.info("✅ LLM配置重新加载完成")
            return True
        except Exception as e:
            logger.error(f"❌ 重新加载配置失败: {e}")
            return False
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """获取可用的LLM提供商列表"""
        providers: List[Dict[str, Any]] = []

        for provider, config in self.SUPPORTED_LLMS.items():
            has_api_key = (provider == LLMProvider.OLLAMA) or (provider in self._api_keys)
            models_registry = self._get_provider_models(provider, config)

            provider_info = {
                "provider": provider.value,
                "name": config["name"],
                "available": has_api_key,
                "default_model": config["default_model"],
                "models": list(models_registry.keys()),
                "api_key_required": config.get("api_key_env"),
                "mode_defaults": dict(config.get("mode_defaults", {}))
            }

            models_detail: Dict[str, Any] = {}
            for model_name in models_registry:
                try:
                    models_detail[model_name] = self.get_llm_info(provider, model_name)
                except ValueError:
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
        """获取指定提供商的模型注册信息"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")

        config = self.SUPPORTED_LLMS[provider]
        models_registry = self._get_provider_models(provider, config)

        available = (provider == LLMProvider.OLLAMA) or (provider in self._api_keys)

        return {
            "provider": provider.value,
            "name": config["name"],
            "models": models_registry,
            "default_model": config["default_model"],
            "available": available,
            "mode_defaults": dict(config.get("mode_defaults", {}))
        }


    def validate_model(self, provider: Union[str, LLMProvider], model: str) -> bool:
        """验证模型是否受支持"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        if provider not in self.SUPPORTED_LLMS:
            return False

        # For Ollama, we don't validate against a fixed list since models are local
        if provider == LLMProvider.OLLAMA:
            return True

        models_registry = self._get_provider_models(provider, self.SUPPORTED_LLMS[provider])
        return model in models_registry


    def create_llm(
        self, 
        provider: Union[str, LLMProvider], 
        model: str = None,
        api_key: str = None,
        **kwargs
    ):
        """
        创建LLM实例
        
        Args:
            provider: LLM提供商
            model: 模型名称，为None时使用默认模型
            api_key: API密钥，为None时使用配置中的密钥
            **kwargs: 其他参数
        
        Returns:
            LLM实例
        """
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        
        config = self.SUPPORTED_LLMS[provider]
        
        # 确定API密钥（Ollama不需要API密钥）
        if provider != LLMProvider.OLLAMA:
            if not api_key:
                api_key = self._api_keys.get(provider)
                if not api_key:
                    raise ValueError(f"未找到{config['name']}的API密钥，请设置环境变量 {config['api_key_env']}")
        
        # 确定模型
        if not model:
            model = config["default_model"]
        
        # 验证模型
        if not self.validate_model(provider, model):
            raise ValueError(f"模型 {model} 不受{config['name']}支持")
        
        # 创建LLM实例
        if provider == LLMProvider.ZHIPU:
            llm_wrapper = ZhipuAILLM(api_key=api_key, model=model, **kwargs)
            return llm_wrapper.create_llm()
            
        elif provider == LLMProvider.OPENAI:
            # 检查是否有自定义base_url
            from ...config import settings
            base_url = settings.openai_base_url or kwargs.get('base_url')
            return build_openai_chat(api_key=api_key, model=model, base_url=base_url, **kwargs)
        
        elif provider == LLMProvider.OLLAMA:
            # 动态导入Ollama LLM类
            try:
                from .instances.ollama_llm import OllamaLLM
                llm_wrapper = OllamaLLM(model=model, **kwargs)
                return llm_wrapper.create_llm()
            except ImportError as e:
                raise ImportError(f"无法导入Ollama LLM: {e}")
        
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def get_llm_info(self, provider: Union[str, LLMProvider], model: str = None) -> Dict[str, Any]:
        """获取LLM信息（包含模型配置与可用性）"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)

        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")

        provider_config = self.SUPPORTED_LLMS[provider]
        models_registry = self._get_provider_models(provider, provider_config)

        # For Ollama, if model is not in the registry, provide generic info
        if provider == LLMProvider.OLLAMA and model and model not in models_registry:
            models_registry[model] = {
                "name": model,
                "description": f"Ollama本地部署模型: {model}",
                "supports_tools": True, 
                "recommended": False
            }

        if model is None:
            model = provider_config["default_model"]

        if model not in models_registry:
            raise ValueError(f"模型 {model} 不受 {provider_config['name']} 支持")

        model_config = models_registry.get(model, {})
        available = (provider == LLMProvider.OLLAMA) or (provider in self._api_keys)

        mode_defaults = self._merge_mode_defaults(
            provider_config.get("mode_defaults"),
            model_config.get("mode_overrides")
        )

        model_features = list(model_config.get("model_features") or [])

        info: Dict[str, Any] = {
            "provider": provider.value,
            "provider_name": provider_config["name"],
            "model": model,
            "model_name": model_config.get("name", model),
            "name": model_config.get("name", model),
            "description": model_config.get("description", ""),
            "available": available,
            "recommended": model_config.get("recommended", False),
            "model_features": model_features,
            "supports_tools": model_config.get("supports_tools", False),
            "mode_defaults": mode_defaults
        }

        if "default_temperature" in model_config:
            info["default_temperature"] = model_config["default_temperature"]
        if "temperature_fixed" in model_config:
            info["temperature_fixed"] = model_config["temperature_fixed"]
        if "max_tokens" in model_config:
            info["max_tokens"] = model_config["max_tokens"]
        if "max_output_tokens" in model_config:
            info["max_output_tokens"] = model_config["max_output_tokens"]
        if "max_output" in model_config:
            info["max_output"] = model_config["max_output"]
        if "parameters" in model_config:
            info["parameters"] = model_config["parameters"]
        if "tags" in model_config:
            info["tags"] = list(model_config["tags"])

        return info


    def set_api_key(self, provider: Union[str, LLMProvider], api_key: str):
        """设置API密钥"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        
        # 基本验证
        config = self.SUPPORTED_LLMS[provider]
        llm_class = config["class"]
        
        if hasattr(llm_class, 'validate_api_key'):
            if not llm_class.validate_api_key(api_key):
                logger.warning(f"{config['name']} API密钥格式可能不正确")
        
        self._api_keys[provider] = api_key
        logger.info(f"已设置{config['name']}的API密钥")
    
    def get_recommended_models(self) -> List[Dict[str, Any]]:
        """获取推荐模型列表"""
        recommended: List[Dict[str, Any]] = []

        for provider, config in self.SUPPORTED_LLMS.items():
            provider_available = (provider == LLMProvider.OLLAMA) or (provider in self._api_keys)
            if not provider_available:
                continue

            models_registry = self._get_provider_models(provider, config)
            for model_name in models_registry:
                info = self.get_llm_info(provider, model_name)
                if info.get("recommended"):
                    recommended.append({
                        "provider": info["provider"],
                        "provider_name": info["provider_name"],
                        "model": info["model"],
                        "model_name": info["model_name"],
                        "description": info["description"]
                    })

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