"""
环境变量加载模块（增强版）

安全加载 .env 文件，支持多层加载：
1. 全局 ~/.iris/.env
2. 项目本地 .env

高优先级的文件会覆盖低优先级的值
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger(__name__)

# 支持的编码列表
SUPPORTED_ENCODINGS = ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gbk", "gb2312"]


def _load_with_fallback(env_path: Path, override: bool = True) -> bool:
    """
    尝试多种编码加载 .env 文件

    Args:
        env_path: .env 文件路径
        override: 是否覆盖已存在的环境变量

    Returns:
        True 如果成功加载，False 否则
    """
    if not env_path.exists():
        return False

    for encoding in SUPPORTED_ENCODINGS:
        try:
            load_dotenv(env_path, encoding=encoding, override=override)
            logger.debug("Loaded %s with encoding: %s", env_path, encoding)
            return True
        except (UnicodeDecodeError, FileNotFoundError):
            continue

    logger.debug("Could not read %s with any supported encoding", env_path)
    return False


def get_global_env_path() -> Path:
    """获取全局 .env 文件路径"""
    return Path.home() / ".iris" / ".env"


def safe_load_dotenv(include_global: bool = True, project_path: Optional[Path] = None) -> List[Path]:
    """
    安全加载 .env 文件

    加载顺序（低优先级 → 高优先级）：
    1. ~/.iris/.env (全局配置)
    2. 项目根目录 .env (本地配置，覆盖全局)

    Args:
        include_global: 是否加载全局 .env
        project_path: 项目路径，如果为 None 则使用 find_dotenv() 查找

    Returns:
        成功加载的 .env 文件路径列表
    """
    loaded_files: List[Path] = []

    # 1. 加载全局 .env（低优先级）
    if include_global:
        global_env = get_global_env_path()
        if global_env.exists():
            if _load_with_fallback(global_env, override=False):
                loaded_files.append(global_env)
                logger.debug("Loaded global env: %s", global_env)

    # 2. 加载项目本地 .env（高优先级，覆盖全局）
    if project_path:
        local_env = project_path / ".env"
    else:
        local_env_str = find_dotenv()
        local_env = Path(local_env_str) if local_env_str else None

    if local_env and local_env.exists():
        if _load_with_fallback(local_env, override=True):
            loaded_files.append(local_env)
            logger.debug("Loaded local env: %s", local_env)

    if not loaded_files:
        logger.debug("No .env files found, using system environment variables")

    return loaded_files


def load_env_for_project(project_path: Path) -> List[Path]:
    """
    为指定项目加载环境变量

    Args:
        project_path: 项目根目录路径

    Returns:
        成功加载的 .env 文件路径列表
    """
    return safe_load_dotenv(include_global=True, project_path=project_path)


# 模块加载时自动执行（保持向后兼容）
# 注意：这会在 import 时自动加载全局和本地 .env
_loaded_files = safe_load_dotenv()
