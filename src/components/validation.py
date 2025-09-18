"""
配置验证模块

提供配置验证和错误处理功能
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None
    JSONSCHEMA_AVAILABLE = False

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self, schema_file: str = "config/llms/schema.json"):
        """
        初始化配置验证器
        
        Args:
            schema_file: JSON Schema文件路径
        """
        self.schema_file = Path(schema_file)
        self._schema = None
        self._load_schema()
    
    def _load_schema(self):
        """加载JSON Schema"""
        try:
            if not self.schema_file.exists():
                logger.warning(f"Schema文件不存在: {self.schema_file}")
                return
            
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                self._schema = json.load(f)
            
            logger.debug(f"Schema已加载: {self.schema_file}")
            
        except Exception as e:
            logger.error(f"加载Schema失败: {e}")
            self._schema = None
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        验证配置
        
        Args:
            config: 要验证的配置
            
        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        
        # 基础结构验证
        basic_errors = self._validate_basic_structure(config)
        errors.extend(basic_errors)
        
        # JSON Schema验证
        if self._schema:
            schema_errors = self._validate_with_schema(config)
            errors.extend(schema_errors)
        else:
            logger.warning("未找到Schema，跳过严格验证")
        
        # 业务逻辑验证
        business_errors = self._validate_business_logic(config)
        errors.extend(business_errors)
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _validate_basic_structure(self, config: Dict[str, Any]) -> List[str]:
        """验证基础结构"""
        errors = []
        
        # 检查必需字段
        if "schema_version" not in config:
            errors.append("缺少必需字段: schema_version")
        
        if "providers" not in config:
            errors.append("缺少必需字段: providers")
            return errors  # 没有providers就没必要继续验证了
        
        if not isinstance(config["providers"], dict):
            errors.append("providers字段必须是字典类型")
            return errors
        
        # 验证每个provider
        for provider_key, provider_config in config["providers"].items():
            provider_errors = self._validate_provider(provider_key, provider_config)
            errors.extend(provider_errors)
        
        return errors
    
    def _validate_provider(self, provider_key: str, provider_config: Any) -> List[str]:
        """验证单个provider配置"""
        errors = []
        prefix = f"Provider '{provider_key}'"
        
        if not isinstance(provider_config, dict):
            errors.append(f"{prefix}: 配置必须是字典类型")
            return errors
        
        # 检查必需字段
        required_fields = ["name", "default_model", "mode_defaults", "models"]
        for field in required_fields:
            if field not in provider_config:
                errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        
        # 验证mode_defaults结构
        if "mode_defaults" in provider_config:
            mode_defaults = provider_config["mode_defaults"]
            if not isinstance(mode_defaults, dict):
                errors.append(f"{prefix}: mode_defaults必须是字典类型")
            else:
                # 检查是否包含llm和agent模式
                expected_modes = ["llm", "agent"]
                for mode in expected_modes:
                    if mode not in mode_defaults:
                        errors.append(f"{prefix}: mode_defaults缺少 '{mode}' 模式配置")
        
        # 验证models结构
        if "models" in provider_config:
            models = provider_config["models"]
            if not isinstance(models, dict):
                errors.append(f"{prefix}: models必须是字典类型")
            else:
                for model_key, model_config in models.items():
                    model_errors = self._validate_model(provider_key, model_key, model_config)
                    errors.extend(model_errors)
        
        return errors
    
    def _validate_model(self, provider_key: str, model_key: str, model_config: Any) -> List[str]:
        """验证单个模型配置"""
        errors = []
        prefix = f"Provider '{provider_key}' Model '{model_key}'"
        
        if not isinstance(model_config, dict):
            errors.append(f"{prefix}: 配置必须是字典类型")
            return errors
        
        # 检查必需字段
        required_fields = ["name", "description", "supports_tools"]
        for field in required_fields:
            if field not in model_config:
                errors.append(f"{prefix}: 缺少必需字段 '{field}'")
        
        # 验证字段类型
        if "supports_tools" in model_config:
            if not isinstance(model_config["supports_tools"], bool):
                errors.append(f"{prefix}: supports_tools必须是布尔类型")
        
        if "recommended" in model_config:
            if not isinstance(model_config["recommended"], bool):
                errors.append(f"{prefix}: recommended必须是布尔类型")
        
        if "model_features" in model_config:
            features = model_config["model_features"]
            if not isinstance(features, list):
                errors.append(f"{prefix}: model_features必须是数组类型")
            elif not all(isinstance(f, str) for f in features):
                errors.append(f"{prefix}: model_features所有元素必须是字符串")
        
        return errors
    
    def _validate_with_schema(self, config: Dict[str, Any]) -> List[str]:
        """使用JSON Schema验证"""
        errors = []
        
        if not JSONSCHEMA_AVAILABLE:
            logger.warning("jsonschema库不可用，跳过Schema验证")
            return errors
        
        try:
            jsonschema.validate(instance=config, schema=self._schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema验证失败: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema文件格式错误: {e.message}")
        except Exception as e:
            errors.append(f"Schema验证异常: {str(e)}")
        
        return errors
    
    def _validate_business_logic(self, config: Dict[str, Any]) -> List[str]:
        """验证业务逻辑"""
        errors = []
        
        providers = config.get("providers", {})
        
        # 验证每个provider的default_model在其models中存在
        for provider_key, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue
            
            default_model = provider_config.get("default_model")
            models = provider_config.get("models", {})
            
            if default_model and isinstance(models, dict):
                # 对于OLLAMA，default_model可以是"auto"，不需要在models中定义
                if provider_key.upper() == "OLLAMA" and default_model == "auto":
                    continue
                
                if default_model not in models:
                    errors.append(f"Provider '{provider_key}': default_model '{default_model}' 不在models列表中")
        
        return errors
    
    def validate_and_fix(self, config: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
        """
        验证配置并尝试修复常见问题
        
        Args:
            config: 原始配置
            
        Returns:
            (修复后的配置, 警告列表)
        """
        warnings = []
        fixed_config = config.copy()
        
        # 修复常见问题
        providers = fixed_config.get("providers", {})
        
        for provider_key, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue
            
            # 确保models字段存在
            if "models" not in provider_config:
                provider_config["models"] = {}
                warnings.append(f"Provider '{provider_key}': 添加了缺失的models字段")
            
            # 确保mode_defaults存在
            if "mode_defaults" not in provider_config:
                provider_config["mode_defaults"] = {
                    "llm": {"temperature": 0.1, "streaming": True},
                    "agent": {"temperature": 0.1, "memory_enabled": True, "max_iterations": 10}
                }
                warnings.append(f"Provider '{provider_key}': 添加了默认的mode_defaults配置")
            
            # 为每个模型添加默认的supports_tools字段
            models = provider_config.get("models", {})
            for model_key, model_config in models.items():
                if isinstance(model_config, dict) and "supports_tools" not in model_config:
                    model_config["supports_tools"] = True
                    warnings.append(f"Provider '{provider_key}' Model '{model_key}': 添加了默认的supports_tools=True")
        
        return fixed_config, warnings


# 全局验证器实例
config_validator = ConfigValidator()


def validate_llm_config(config: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    验证LLM配置的便捷函数
    
    Args:
        config: 要验证的配置
        
    Returns:
        (是否有效, 错误列表)
    """
    return config_validator.validate_config(config)


def validate_and_fix_config(config: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """
    验证并修复配置的便捷函数
    
    Args:
        config: 原始配置
        
    Returns:
        (修复后的配置, 警告列表)
    """
    return config_validator.validate_and_fix(config)
