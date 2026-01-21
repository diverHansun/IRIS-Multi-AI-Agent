"""
IRIS 配置管理模块

提供三层配置架构：
1. 环境变量 + .env 文件（最高优先级）
2. 项目级配置 (<project>/.iris/)
3. 用户级配置 (~/.iris/)
4. 内置默认配置（最低优先级）

使用示例：

    # 获取配置
    from src.core.config import get_config
    config = get_config()

    # 获取 API key
    api_key = config.get_api_key("zhipu")

    # 获取默认设置
    provider = config.defaults.llm_provider
    model = config.defaults.llm_model

    # 使用旧接口（向后兼容）
    from src.core.config import settings
    if settings.has_zhipu():
        ...
"""

# 首先加载环境变量
from .env_loader import safe_load_dotenv, load_env_for_project, get_global_env_path

# 配置模型
from .models import (
    IrisConfig,
    APIKeysConfig,
    DefaultsConfig,
    DisplayConfig,
    MCPConfig,
    DeepAgentConfig,
    OllamaConfig,
    PathsConfig,
)

# 配置加载器
from .loader import (
    ConfigLoader,
    get_config_loader,
    get_config,
    reload_config,
    set_project_context,
)

# 初始化器
from .initializer import (
    ConfigInitializer,
    ensure_initialized,
    reset_config,
)

# 环境变量解析器
from .resolver import EnvResolver

# 默认配置
from .defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_TOML, CONFIG_MIGRATION_MAPPING

# 设置（向后兼容）
from .settings import Settings, settings, reload_settings

__all__ = [
    # 环境变量加载
    "safe_load_dotenv",
    "load_env_for_project",
    "get_global_env_path",
    # 配置模型
    "IrisConfig",
    "APIKeysConfig",
    "DefaultsConfig",
    "DisplayConfig",
    "MCPConfig",
    "DeepAgentConfig",
    "OllamaConfig",
    "PathsConfig",
    # 配置加载器
    "ConfigLoader",
    "get_config_loader",
    "get_config",
    "reload_config",
    "set_project_context",
    # 初始化器
    "ConfigInitializer",
    "ensure_initialized",
    "reset_config",
    # 环境变量解析器
    "EnvResolver",
    # 默认配置
    "DEFAULT_CONFIG",
    "DEFAULT_CONFIG_TOML",
    "CONFIG_MIGRATION_MAPPING",
    # 设置（向后兼容）
    "Settings",
    "settings",
    "reload_settings",
]
