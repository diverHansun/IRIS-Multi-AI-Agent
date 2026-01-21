"""
三层配置加载器

按优先级加载和合并配置：
1. 环境变量 + .env 文件
2. 项目级配置 (<project>/.iris/)
3. 用户级配置 (~/.iris/)
4. 内置默认配置
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

from .defaults import DEFAULT_CONFIG
from .paths import find_config_dir, resolve_config_path
from .models import IrisConfig
from .resolver import EnvResolver

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """安全加载 JSON 文件"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load JSON file %s: %s", path, e)
        return None


def _load_toml_file(path: Path) -> Optional[Dict[str, Any]]:
    """安全加载 TOML 文件"""
    if not path.exists():
        return None
    try:
        import tomlkit

        content = path.read_text(encoding="utf-8")
        return dict(tomlkit.loads(content))
    except ImportError:
        # tomlkit 不可用，尝试使用标准库 tomllib (Python 3.11+)
        try:
            import tomllib

            content = path.read_bytes()
            return tomllib.loads(content.decode("utf-8"))
        except ImportError:
            logger.warning("Neither tomlkit nor tomllib available, cannot load TOML")
            return None
    except Exception as e:
        logger.warning("Failed to load TOML file %s: %s", path, e)
        return None


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并两个字典

    overlay 中的值会覆盖 base 中的值
    """
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_relative_path(relative_path: str) -> str:
    """
    规范化相对路径，去除前缀的 config/（如果存在），并统一为 POSIX 分隔符。
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    if rel.startswith("config/"):
        rel = rel[len("config/") :]
    return rel


class ConfigLoader:
    """
    三层配置加载器

    负责按优先级加载和合并配置：
    1. 环境变量 + .env 文件（最高优先级）
    2. 项目级配置 (<project>/.iris/config.toml)
    3. 用户级配置 (~/.iris/config.toml)
    4. 内置默认配置（最低优先级）
    """

    def __init__(
        self,
        user_config_dir: Optional[Path] = None,
        project_config_dir: Optional[Path] = None,
        env_resolver: Optional[EnvResolver] = None,
    ):
        """
        初始化配置加载器

        Args:
            user_config_dir: 用户配置目录，默认 ~/.iris/
            project_config_dir: 项目配置目录，默认 <project>/.iris/
            env_resolver: 环境变量解析器
        """
        self._user_config_dir = user_config_dir or (Path.home() / ".iris")
        self._project_config_dir = project_config_dir
        self._env_resolver = env_resolver or EnvResolver()
        self._cached_config: Optional[IrisConfig] = None

    @property
    def user_config_dir(self) -> Path:
        """返回用户配置目录"""
        return self._user_config_dir

    @property
    def project_config_dir(self) -> Optional[Path]:
        """返回项目配置目录"""
        return self._project_config_dir

    def set_project_config_dir(self, path: Optional[Path]) -> None:
        """设置项目配置目录"""
        self._project_config_dir = path
        self._cached_config = None  # 清除缓存

    def load(self, force_reload: bool = False) -> IrisConfig:
        """
        加载合并后的配置

        Args:
            force_reload: 强制重新加载，忽略缓存

        Returns:
            合并后的 IrisConfig 实例
        """
        if self._cached_config and not force_reload:
            return self._cached_config

        # 从最低优先级开始，逐层覆盖
        config_data: Dict[str, Any] = {}

        # 4. 内置默认配置
        config_data = _deep_merge(config_data, DEFAULT_CONFIG)
        logger.debug("Loaded default configuration")

        # 3. 用户级配置
        user_config = self._load_user_config()
        if user_config:
            config_data = _deep_merge(config_data, user_config)
            logger.debug("Merged user configuration from %s", self._user_config_dir)

        # 2. 项目级配置
        if self._project_config_dir:
            project_config = self._load_project_config()
            if project_config:
                config_data = _deep_merge(config_data, project_config)
                logger.debug(
                    "Merged project configuration from %s", self._project_config_dir
                )

        # 1. 环境变量覆盖
        env_overrides = self._get_env_overrides()
        if env_overrides:
            config_data = _deep_merge(config_data, env_overrides)
            logger.debug("Applied environment variable overrides")

        # 解析所有 ${VAR} 引用
        config_data = self._env_resolver.resolve_all(config_data)

        # 构建最终配置对象
        self._cached_config = IrisConfig.model_validate(config_data)
        return self._cached_config

    def _load_user_config(self) -> Optional[Dict[str, Any]]:
        """加载用户级配置"""
        config_file = self._user_config_dir / "config.toml"
        return _load_toml_file(config_file)

    def _load_project_config(self) -> Optional[Dict[str, Any]]:
        """加载项目级配置"""
        if not self._project_config_dir:
            return None
        config_file = self._project_config_dir / "config.toml"
        return _load_toml_file(config_file)

    def _get_env_overrides(self) -> Dict[str, Any]:
        """从环境变量获取覆盖值"""
        import os

        overrides: Dict[str, Any] = {"api_keys": {}, "defaults": {}, "ollama": {}}

        # API Keys
        env_mapping = {
            "ZHIPU_API_KEY": "zhipu_api_key",
            "OPENAI_API_KEY": "openai_api_key",
            "ANTHROPIC_API_KEY": "anthropic_api_key",
            "TONGYI_API_KEY": "tongyi_api_key",
            "TAVILY_API_KEY": "tavily_api_key",
            "AMAP_API_KEY": "amap_api_key",
            "NOTION_TOKEN": "notion_token",
        }

        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                overrides["api_keys"][config_key] = value

        # 默认设置
        if os.getenv("DEFAULT_LLM_PROVIDER"):
            overrides["defaults"]["llm_provider"] = os.getenv("DEFAULT_LLM_PROVIDER")
        if os.getenv("DEFAULT_LLM_MODEL"):
            overrides["defaults"]["llm_model"] = os.getenv("DEFAULT_LLM_MODEL")
        if os.getenv("ENABLE_STREAMING_BY_DEFAULT"):
            overrides["defaults"]["streaming"] = (
                os.getenv("ENABLE_STREAMING_BY_DEFAULT", "").lower() == "true"
            )

        # Ollama 配置
        if os.getenv("OLLAMA_BASE_URL"):
            overrides["ollama"]["base_url"] = os.getenv("OLLAMA_BASE_URL")
        if os.getenv("OLLAMA_TIMEOUT"):
            overrides["ollama"]["timeout"] = int(os.getenv("OLLAMA_TIMEOUT", "60"))
        if os.getenv("DEFAULT_OLLAMA_MODEL"):
            overrides["ollama"]["default_model"] = os.getenv("DEFAULT_OLLAMA_MODEL")

        # 清理空字典
        return {k: v for k, v in overrides.items() if v}

    def reload(self) -> IrisConfig:
        """强制重新加载配置"""
        return self.load(force_reload=True)

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        获取 API Key

        Args:
            provider: 提供商名称 (zhipu, openai, etc.)

        Returns:
            API key 字符串，如果未配置则返回 None
        """
        config = self.load()
        return config.get_api_key(provider)

    def has_api_key(self, provider: str) -> bool:
        """
        检查是否配置了 API Key

        Args:
            provider: 提供商名称

        Returns:
            True 如果已配置
        """
        config = self.load()
        return config.has_api_key(provider)

    # =========================================================================
    # JSON 配置文件加载
    # =========================================================================

    def load_json_config(
        self, relative_path: str, merge_project: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        加载 JSON 配置文件

        按优先级合并：用户级 < 项目级

        Args:
            relative_path: 相对于配置目录的路径
            merge_project: 是否合并项目级配置

        Returns:
            合并后的配置字典
        """
        rel_path = _normalize_relative_path(relative_path)
        config: Dict[str, Any] = {}

        # 用户级配置
        user_file = self._user_config_dir / rel_path
        user_config = _load_json_file(user_file)
        if user_config:
            config = _deep_merge(config, user_config)

        # 项目级配置
        if merge_project and self._project_config_dir:
            project_file = self._project_config_dir / rel_path
            project_config = _load_json_file(project_file)
            if project_config:
                config = _deep_merge(config, project_config)

        return config if config else None

    def load_providers_config(self) -> Optional[Dict[str, Any]]:
        """加载 LLM providers 配置"""
        return self.load_json_config("llm/providers.json")

    def load_basic_agent_config(self) -> Optional[Dict[str, Any]]:
        """加载 Basic Agent 配置"""
        return self.load_json_config("agents/basic/providers.json")

    def load_deep_agent_subagents(self) -> Optional[Dict[str, Any]]:
        """加载 Deep Agent 子代理配置"""
        return self.load_json_config("agents/deep/subagents.json")

    def load_deep_agent_mainagents(self) -> Optional[Dict[str, Any]]:
        """加载 Deep Agent 主代理配置"""
        return self.load_json_config("agents/deep/mainagents.json")

    # =========================================================================
    # 路径解析与回退加载
    # =========================================================================

    def resolve_config_path(
        self, relative_path: str, *, project_first: bool = True
    ) -> Optional[Path]:
        """
        按优先级解析配置文件路径（项目 -> 用户 -> 内置）
        """
        fallback_dirs = []
        config_dir = find_config_dir()
        if config_dir:
            fallback_dirs.append(config_dir)

        return resolve_config_path(
            relative_path,
            project_dir=self._project_config_dir,
            user_dir=self._user_config_dir,
            fallback_dirs=fallback_dirs,
            project_first=project_first,
        )

    def load_shared_json(
        self, relative_path: str, *, merge_project: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        加载 JSON 配置，优先使用 .iris（项目/用户），缺失时回退到内置 config。
        """
        # 优先从 .iris（用户+项目）加载并合并
        data = self.load_json_config(relative_path, merge_project=merge_project)
        if data:
            return data

        # 回退到内置 config
        fallback_path = self.resolve_config_path(relative_path, project_first=merge_project)
        if fallback_path and fallback_path.exists():
            return _load_json_file(fallback_path)
        return None


# =========================================================================
# 全局配置加载器实例
# =========================================================================

_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """获取全局配置加载器"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def get_config() -> IrisConfig:
    """获取当前配置（便捷方法）"""
    return get_config_loader().load()


def reload_config() -> IrisConfig:
    """重新加载配置（便捷方法）"""
    return get_config_loader().reload()


def set_project_context(project_iris_dir: Optional[Path]) -> None:
    """
    设置项目上下文

    Args:
        project_iris_dir: 项目的 .iris 目录路径
    """
    loader = get_config_loader()
    loader.set_project_config_dir(project_iris_dir)
