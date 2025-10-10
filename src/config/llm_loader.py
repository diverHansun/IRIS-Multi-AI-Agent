"""
LLM配置加载模块

从JSON文件加载和管理LLM配置
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class LLMConfigLoader:
    """LLM配置加载器，从JSON文件加载模型配置"""

    def __init__(self, config_dir: str = "config/llms"):
        """
        初始化配置加载器

        Args:
            config_dir: 配置目录路径
        """
        self.config_dir = Path(config_dir)
        self.providers_file = self.config_dir / "providers.json"
        self.schema_file = self.config_dir / "schema.json"
        self._cached_config = None
        self._cache_timestamp = None

    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        加载配置，如果缓存有效则返回缓存

        Args:
            force_reload: 是否强制重新加载

        Returns:
            配置字典
        """
        if not force_reload and self._cached_config is not None:
            # 检查文件是否被修改
            if self._is_cache_valid():
                return self._cached_config

        try:
            config = self._load_from_file()
            self._validate_config(config)
            self._cached_config = config
            self._cache_timestamp = self._get_file_timestamp()
            logger.info(f"[OK] 配置已从 {self.providers_file} 加载")
            return config
        except Exception as e:
            logger.error(f"[ERROR] 加载配置失败: {e}")
            raise

    def _load_from_file(self) -> Dict[str, Any]:
        """从文件加载配置"""
        if not self.providers_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.providers_file}")

        with open(self.providers_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """验证配置格式"""
        try:
            # 尝试导入验证器（使用安全的导入方式）
            import importlib.util
            from pathlib import Path

            # 直接加载validation模块，避免src包的初始化问题
            validation_path = Path(__file__).parent.parent / "components" / "process" / "validation.py"
            spec = importlib.util.spec_from_file_location("validation_module", validation_path)
            validation_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(validation_module)

            validate_llm_config = validation_module.validate_llm_config
            validate_and_fix_config = validation_module.validate_and_fix_config

            # 验证配置
            is_valid, errors = validate_llm_config(config)

            if not is_valid:
                # 尝试修复配置
                fixed_config, warnings = validate_and_fix_config(config)

                # 再次验证修复后的配置
                is_valid_after_fix, remaining_errors = validate_llm_config(fixed_config)

                if is_valid_after_fix:
                    # 使用修复后的配置
                    config.clear()
                    config.update(fixed_config)

                    # 记录警告
                    for warning in warnings:
                        logger.warning(f"配置修复: {warning}")

                    logger.info("[OK] 配置验证通过（已自动修复部分问题）")
                else:
                    # 修复后仍有错误
                    error_msg = "配置验证失败，无法自动修复:\n" + "\n".join(remaining_errors)
                    raise ValueError(error_msg)
            else:
                logger.debug("[OK] 配置验证通过")

        except ImportError:
            # 如果验证器不可用，使用基础验证
            logger.warning("配置验证器不可用，使用基础验证")
            self._basic_validate_config(config)

    def _basic_validate_config(self, config: Dict[str, Any]) -> None:
        """基础配置验证（验证器不可用时的后备方案）"""
        if "schema_version" not in config:
            raise ValueError("配置文件缺少 schema_version 字段")

        if "providers" not in config:
            raise ValueError("配置文件缺少 providers 字段")

        if not isinstance(config["providers"], dict):
            raise ValueError("providers 字段必须是字典类型")

        # 验证每个provider的基本结构
        for provider_key, provider_config in config["providers"].items():
            if not isinstance(provider_config, dict):
                raise ValueError(f"Provider {provider_key} 配置必须是字典类型")

            required_fields = ["name", "default_model", "mode_defaults", "models"]
            for field in required_fields:
                if field not in provider_config:
                    raise ValueError(f"Provider {provider_key} 缺少必需字段: {field}")

    def _is_cache_valid(self) -> bool:
        """检查缓存是否仍然有效"""
        if self._cache_timestamp is None:
            return False

        current_timestamp = self._get_file_timestamp()
        return current_timestamp == self._cache_timestamp

    def _get_file_timestamp(self) -> Optional[float]:
        """获取配置文件的时间戳"""
        try:
            return self.providers_file.stat().st_mtime
        except (OSError, FileNotFoundError):
            return None

    def reload_config(self) -> Dict[str, Any]:
        """强制重新加载配置"""
        logger.info("[RELOAD] 重新加载LLM配置...")
        self._cached_config = None
        self._cache_timestamp = None
        return self.load_config(force_reload=True)

    def get_provider_config(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """获取指定provider的配置"""
        config = self.load_config()
        return config["providers"].get(provider_key)

    def list_providers(self) -> Dict[str, Any]:
        """列出所有可用的providers"""
        config = self.load_config()
        return config["providers"]


# 全局配置加载器实例
config_loader = LLMConfigLoader()
