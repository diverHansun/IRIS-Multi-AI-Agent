"""
LLM Manager - 统一LLM管理接口

提供统一的LLM选择、创建和管理功能
支持多个LLM提供商（智谱AI、OpenAI等）
"""

import logging
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from .zhipu_llm import ZhipuAILLM
from .openai_llm import OpenAILLM, build_openai_chat
from ..config import settings

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    """LLM提供商枚举"""
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"

class LLMManager:
    """LLM管理器"""
    
    # 支持的LLM配置
    SUPPORTED_LLMS = {
        LLMProvider.ZHIPU: {
            "name": "智谱AI",
            "models": {
                "glm-4-plus": {
                    "name": "GLM-4-Plus",
                    "description": "智谱AI最新旗舰模型，综合能力强",
                    "max_tokens": 8192,
                    "context_window": 32000,
                    "recommended": True
                },
                "glm-4.5": {
                    "name": "GLM-4.5",
                    "description": "智谱AI新一代MoE架构模型，支持128K上下文，专精代码推理和工具调用",
                    "max_tokens": 96000,  # GLM-4.5支持高达96K输出token
                    "context_window": 128000,  # 128K上下文窗口
                    "recommended": True,
                    "features": ["thinking_mode", "tool_calling", "code_generation", "long_context"],
                    "architecture": "mixture_of_experts"
                }
            },
            "default_model": "glm-4-plus",
            "api_key_env": "ZHIPU_API_KEY",
            "class": ZhipuAILLM
        },
        LLMProvider.OPENAI: {
            "name": "OpenAI",
            "models": {
                "gpt-5": {
                    "name": "GPT-5",
                    "description": "新一代语言模型，推理和创造能力显著提升",
                    "max_tokens": 8192,
                    "context_window": 8192,
                    "recommended": True,
                    "features": ["advanced_reasoning", "enhanced_creativity", "improved_tool_calling", "multimodal"],
                    "architecture": "next_generation",
                    "default_temperature": 1.0,
                    "temperature_fixed": True
                },
                "gpt-5-mini": {
                    "name": "GPT-5-mini",
                    "description": "成本优化版本，速度快成本低",
                    "max_tokens": 32768,
                    "context_window": 32768,
                    "recommended": True,
                    "features": ["fast_inference", "cost_optimized", "tool_calling", "multimodal"],
                    "architecture": "optimized",
                    "default_temperature": 1.0,
                    "temperature_fixed": True
                },
                "gpt-4o": {
                    "name": "GPT-4o",
                    "description": "OpenAI最新GPT-4优化版本，性能和成本平衡",
                    "max_tokens": 4096,
                    "context_window": 131072,
                    "recommended": True,
                    "features": ["multimodal", "long_context", "cost_optimized"]
                },
                "gpt-4o-mini": {
                    "name": "GPT-4o-mini",
                    "description": "轻量级版本，速度快成本低",
                    "max_tokens": 16384,
                    "context_window": 131072,
                    "recommended": True,
                    "features": ["multimodal", "long_context", "fast_inference", "cost_optimized"]
                },
                "gpt-4-turbo": {
                    "name": "GPT-4-turbo",
                    "description": "高性能版本",
                    "max_tokens": 4096,
                    "recommended": False
                }
            },
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "class": OpenAILLM
        },
        LLMProvider.OLLAMA: {
            "name": "Ollama本地模型",
            "models": {
                "gpt-oss:20b": {
                    "name": "GPT-OSS-20B",
                    "description": "开源GPT模型，20B参数，强大的通用对话能力",
                    "max_tokens": 8192,
                    "context_window": 32768,
                    "recommended": True,
                    "features": ["chat", "reasoning", "large_model"]
                },
                "qwen3:8b": {
                    "name": "Qwen3-8B",
                    "description": "阿里巴巴通义千问3.0模型，中文优化，综合能力强",
                    "max_tokens": 32768,
                    "context_window": 32768,
                    "recommended": True,
                    "features": ["chinese_optimized", "chat", "reasoning"]
                },
                "gemma3:latest": {
                    "name": "Gemma3-Latest",
                    "description": "Google Gemma3模型最新版本，高效轻量",
                    "max_tokens": 8192,
                    "context_window": 32768,
                    "recommended": True,
                    "features": ["efficient", "chat", "reasoning"]
                },
                "deepseek-r1:1.5b": {
                    "name": "DeepSeek-R1-1.5B",
                    "description": "DeepSeek推理模型，专注逻辑推理和数学计算",
                    "max_tokens": 4096,
                    "context_window": 16384,
                    "recommended": False,
                    "features": ["reasoning", "mathematics", "lightweight"]
                }
            },
            "default_model": "gpt-oss:20b",
            "api_key_env": None,  # Ollama不需要API密钥
            "class": None  # 稍后导入避免循环依赖
        }
    }
    
    def __init__(self):
        """初始化LLM管理器"""
        self._api_keys = {}
        self._load_api_keys()
    
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
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """获取可用的LLM提供商列表"""
        providers = []
        
        for provider, config in self.SUPPORTED_LLMS.items():
            # Ollama不需要API密钥，始终可用
            if provider == LLMProvider.OLLAMA:
                has_api_key = True
            else:
                has_api_key = provider in self._api_keys
            
            provider_info = {
                "provider": provider.value,
                "name": config["name"],
                "available": has_api_key,
                "default_model": config["default_model"],
                "models": list(config["models"].keys()),
                "api_key_required": config["api_key_env"]
            }
            
            if has_api_key:
                provider_info["models_detail"] = config["models"]
            
            providers.append(provider_info)
        
        return providers
    
    def get_provider_models(self, provider: Union[str, LLMProvider]) -> Dict[str, Any]:
        """获取指定提供商的模型列表"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        
        config = self.SUPPORTED_LLMS[provider]
        # Ollama不需要API密钥，始终可用
        if provider == LLMProvider.OLLAMA:
            available = True
        else:
            available = provider in self._api_keys
        
        return {
            "provider": provider.value,
            "name": config["name"],
            "models": config["models"],
            "default_model": config["default_model"],
            "available": available
        }
    
    def validate_model(self, provider: Union[str, LLMProvider], model: str) -> bool:
        """验证模型是否支持"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.SUPPORTED_LLMS:
            return False
        
        return model in self.SUPPORTED_LLMS[provider]["models"]
    
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
            from ..config import settings
            base_url = settings.openai_base_url or kwargs.get('base_url')
            return build_openai_chat(api_key=api_key, model=model, base_url=base_url, **kwargs)
        
        elif provider == LLMProvider.OLLAMA:
            # 动态导入Ollama LLM类
            try:
                from .ollama_llm import OllamaLLM
                llm_wrapper = OllamaLLM(model=model, **kwargs)
                return llm_wrapper.create_llm()
            except ImportError as e:
                raise ImportError(f"无法导入Ollama LLM: {e}")
        
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def get_model_info(self, provider: Union[str, LLMProvider], model: str) -> Dict[str, Any]:
        """获取指定模型的详细信息"""
        if isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.SUPPORTED_LLMS:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        
        config = self.SUPPORTED_LLMS[provider]
        
        if model not in config["models"]:
            raise ValueError(f"模型 {model} 不受支持")
        
        model_config = config["models"][model]
        
        # Ollama不需要API密钥，始终可用
        if provider == LLMProvider.OLLAMA:
            available = True
        else:
            available = provider in self._api_keys
        
        return {
            "provider": provider.value,
            "provider_name": config["name"],
            "model": model,
            "model_name": model_config["name"],
            "description": model_config["description"],
            "max_tokens": model_config["max_tokens"],
            "recommended": model_config.get("recommended", False),
            "available": available
        }
    
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
        recommended = []
        
        for provider, config in self.SUPPORTED_LLMS.items():
            # Ollama不需要API密钥，始终可用；其他需要API密钥
            provider_available = (provider == LLMProvider.OLLAMA) or (provider in self._api_keys)
            if provider_available:
                for model, model_config in config["models"].items():
                    if model_config.get("recommended", False):
                        recommended.append({
                            "provider": provider.value,
                            "provider_name": config["name"],
                            "model": model,
                            "model_name": model_config["name"],
                            "description": model_config["description"]
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


def get_model_info(provider: str, model: str) -> Dict[str, Any]:
    """获取模型信息的便捷函数"""
    return llm_manager.get_model_info(provider, model)


def get_recommended_models() -> List[Dict[str, Any]]:
    """获取推荐模型"""
    return llm_manager.get_recommended_models()