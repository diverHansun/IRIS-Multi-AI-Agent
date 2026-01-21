"""
环境变量和引用解析器

支持 ${VAR_NAME} 语法解析环境变量引用
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 匹配 ${VAR_NAME} 语法
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class EnvResolver:
    """
    环境变量解析器

    支持：
    - ${VAR_NAME} 语法
    - 多 .env 文件按优先级加载
    - 递归解析嵌套引用
    """

    def __init__(self, env_files: Optional[List[Path]] = None):
        """
        初始化解析器

        Args:
            env_files: .env 文件列表，按优先级从低到高排序
        """
        self._env_cache: Dict[str, str] = {}
        self._env_files = env_files or []
        self._load_env_files()

    def _load_env_files(self) -> None:
        """按优先级加载所有 .env 文件"""
        from dotenv import dotenv_values

        # 从最低优先级开始加载，高优先级覆盖低优先级
        for env_file in self._env_files:
            if env_file.exists():
                try:
                    values = dotenv_values(env_file)
                    self._env_cache.update({k: v for k, v in values.items() if v is not None})
                    logger.debug("Loaded env file: %s", env_file)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", env_file, e)

    def add_env_file(self, path: Path, priority: str = "high") -> None:
        """
        动态添加 .env 文件

        Args:
            path: .env 文件路径
            priority: "high" 覆盖现有，"low" 只填充空值
        """
        from dotenv import dotenv_values

        if not path.exists():
            return

        try:
            values = dotenv_values(path)
            if priority == "high":
                self._env_cache.update({k: v for k, v in values.items() if v is not None})
            else:
                for key, value in values.items():
                    if key not in self._env_cache and value is not None:
                        self._env_cache[key] = value
            logger.debug("Added env file: %s (priority=%s)", path, priority)
        except Exception as e:
            logger.warning("Failed to load %s: %s", path, e)

    def resolve(self, value: str, max_depth: int = 10) -> str:
        """
        解析字符串中的环境变量引用

        Args:
            value: 包含 ${VAR} 的字符串
            max_depth: 最大递归深度

        Returns:
            解析后的字符串
        """
        if not isinstance(value, str) or max_depth <= 0:
            return value

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            # 优先级：OS 环境变量 > 缓存的 .env 值
            env_value = os.getenv(var_name) or self._env_cache.get(var_name, "")
            return env_value

        resolved = ENV_VAR_PATTERN.sub(replacer, value)

        # 递归解析（处理嵌套引用）
        if resolved != value and ENV_VAR_PATTERN.search(resolved):
            return self.resolve(resolved, max_depth - 1)

        return resolved

    def resolve_all(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归解析字典中所有字符串值的环境变量引用

        Args:
            data: 包含配置的字典

        Returns:
            解析后的字典
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.resolve(value)
            elif isinstance(value, dict):
                result[key] = self.resolve_all(value)
            elif isinstance(value, list):
                result[key] = [
                    self.resolve(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result

    def get(self, var_name: str, default: Optional[str] = None) -> Optional[str]:
        """获取环境变量值"""
        return os.getenv(var_name) or self._env_cache.get(var_name, default)

    def has(self, var_name: str) -> bool:
        """检查环境变量是否存在"""
        return bool(os.getenv(var_name) or var_name in self._env_cache)
