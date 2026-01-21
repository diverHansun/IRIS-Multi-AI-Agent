"""
首次运行初始化器

负责：
- 创建 ~/.iris/ 目录结构
- 复制默认配置文件
- 首次运行引导
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .paths import find_config_dir
from .defaults import (
    CONFIG_MIGRATION_MAPPING,
    DEFAULT_CONFIG_TOML,
    DEFAULT_ENV_TEMPLATE,
    REQUIRED_DIRS,
)

logger = logging.getLogger(__name__)


class ConfigInitializer:
    """
    配置初始化器

    负责：
    - 创建 ~/.iris/ 目录结构
    - 复制默认配置模板
    - 首次运行引导
    """

    def __init__(self, share_dir: Optional[Path] = None):
        """
        初始化

        Args:
            share_dir: 共享目录路径，默认为 ~/.iris/
        """
        self._share_dir = share_dir or (Path.home() / ".iris")
        self._config_dir = find_config_dir()

    @property
    def share_dir(self) -> Path:
        """返回共享目录路径"""
        return self._share_dir

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        config_file = self._share_dir / "config.toml"
        return config_file.exists()

    def initialize(
        self, force: bool = False, quiet: bool = False, sync_missing: bool = True
    ) -> bool:
        """
        执行初始化

        Args:
            force: 强制重新初始化（覆盖现有配置）
            quiet: 静默模式，不显示引导信息

        Returns:
            True 表示成功初始化，False 表示已存在或失败
        """
        if self.is_initialized() and not force:
            logger.debug("Configuration already initialized at %s", self._share_dir)
            if sync_missing:
                try:
                    self._create_directories()
                    copied_files = self._copy_config_files()
                    copied_files += self._copy_additional_files()
                    if copied_files and not quiet:
                        self._show_setup_guide(copied_files)
                except Exception as e:
                    logger.warning("Sync missing configs failed: %s", e)
            return False

        try:
            # 1. 创建目录结构
            self._create_directories()

            # 2. 写入默认配置文件
            self._write_default_configs()

            # 3. 复制配置文件
            copied_files = self._copy_config_files()
            copied_files += self._copy_additional_files()

            # 4. 显示设置引导
            if not quiet:
                self._show_setup_guide(copied_files)

            logger.info("Configuration initialized at %s", self._share_dir)
            return True

        except Exception as e:
            logger.error("Failed to initialize configuration: %s", e)
            return False

    def _create_directories(self) -> None:
        """创建必要的目录结构"""
        for dir_name in REQUIRED_DIRS:
            dir_path = self._share_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug("Created directory: %s", dir_path)

    def _write_default_configs(self) -> None:
        """写入默认配置文件"""
        # config.toml
        config_file = self._share_dir / "config.toml"
        if not config_file.exists():
            config_file.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
            logger.debug("Created config.toml")

        # .env.example
        env_example = self._share_dir / ".env.example"
        if not env_example.exists():
            env_example.write_text(DEFAULT_ENV_TEMPLATE, encoding="utf-8")
            logger.debug("Created .env.example")

    def _copy_config_files(self) -> List[Tuple[str, str]]:
        """
        从源码目录复制配置文件到用户目录

        Returns:
            复制成功的文件列表 [(源路径, 目标路径), ...]
        """
        copied_files: List[Tuple[str, str]] = []

        if not self._config_dir:
            logger.warning("Could not find bundled config directory, skipping config copy")
            return copied_files

        for src_relative, dst_relative in CONFIG_MIGRATION_MAPPING.items():
            rel = (
                src_relative[len("config/") :]
                if src_relative.startswith("config/")
                else src_relative
            )
            src_path = self._config_dir / rel
            dst_path = self._share_dir / dst_relative

            if not src_path.exists():
                logger.debug("Source file not found: %s", src_path)
                continue

            if dst_path.exists():
                logger.debug("Destination file already exists: %s", dst_path)
                continue

            try:
                # 确保目标目录存在
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                # 复制文件
                shutil.copy2(src_path, dst_path)
                copied_files.append((str(src_relative), str(dst_relative)))
                logger.debug("Copied: %s -> %s", src_path, dst_path)

            except Exception as e:
                logger.warning("Failed to copy %s: %s", src_path, e)

        return copied_files

    def _copy_additional_files(self) -> List[Tuple[str, str]]:
        """
        复制 config 目录下其余的 JSON/TOML/YAML 配置文件，跳过 *.example.*。
        """
        copied: List[Tuple[str, str]] = []
        if not self._config_dir:
            return copied

        allowed_suffixes = {".json", ".toml", ".yaml", ".yml"}
        for src_path in self._config_dir.rglob("*"):
            if not src_path.is_file():
                continue
            if ".example" in src_path.name:
                continue
            if src_path.suffix.lower() not in allowed_suffixes:
                continue

            rel = src_path.relative_to(self._config_dir)
            dst_path = self._share_dir / rel

            if dst_path.exists():
                continue

            try:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                copied.append(
                    (
                        str(src_path.relative_to(self._config_dir.parent)),
                        str(rel),
                    )
                )
                logger.debug("Copied extra config: %s -> %s", src_path, dst_path)
            except Exception as e:
                logger.warning("Failed to copy extra config %s: %s", src_path, e)

        return copied

    def _show_setup_guide(self, copied_files: List[Tuple[str, str]]) -> None:
        """显示设置引导信息"""
        # 检测是否在终端中运行
        is_tty = sys.stdout.isatty()

        if is_tty:
            self._show_rich_guide(copied_files)
        else:
            self._show_plain_guide(copied_files)

    def _show_rich_guide(self, copied_files: List[Tuple[str, str]]) -> None:
        """使用 rich 显示格式化的引导信息"""
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text

            console = Console()

            # 标题
            title = Text("IRIS Configuration Setup", style="bold cyan")

            # 内容
            content = Text()
            content.append(f"Configuration directory created at:\n", style="dim")
            content.append(f"  {self._share_dir}\n\n", style="green")

            if copied_files:
                content.append(f"Copied {len(copied_files)} configuration files.\n\n", style="dim")

            content.append("Next steps:\n", style="bold yellow")
            content.append("  1. Copy .env.example to .env\n", style="white")
            content.append("  2. Fill in your API keys in .env\n", style="white")
            content.append("  3. Customize config.toml as needed\n\n", style="white")

            content.append("Quick start:\n", style="bold yellow")
            content.append(f"  cd {self._share_dir}\n", style="cyan")
            content.append("  cp .env.example .env\n", style="cyan")
            content.append("  # Edit .env with your API keys\n", style="dim")

            console.print(Panel(content, title=title, border_style="cyan"))

        except ImportError:
            self._show_plain_guide(copied_files)

    def _show_plain_guide(self, copied_files: List[Tuple[str, str]]) -> None:
        """显示纯文本引导信息"""
        print(
            f"""
╔══════════════════════════════════════════════════════════════╗
║                    IRIS Configuration Setup                   ║
╠══════════════════════════════════════════════════════════════╣
║  Configuration directory created at:                          ║
║    {self._share_dir}
║                                                               ║
║  Copied {len(copied_files)} configuration files.
║                                                               ║
║  Next steps:                                                  ║
║  1. Copy .env.example to .env                                 ║
║  2. Fill in your API keys in .env                             ║
║  3. Customize config.toml as needed                           ║
║                                                               ║
║  Quick start:                                                 ║
║    cd {self._share_dir}
║    cp .env.example .env                                       ║
║    # Edit .env with your API keys                             ║
╚══════════════════════════════════════════════════════════════╝
"""
        )


def ensure_initialized(quiet: bool = True) -> bool:
    """
    确保配置已初始化

    首次运行时自动执行初始化

    Args:
        quiet: 静默模式（首次运行后的后续运行不显示引导）

    Returns:
        True 表示配置可用
    """
    initializer = ConfigInitializer()

    if not initializer.is_initialized():
        # 首次运行，显示引导
        return initializer.initialize(quiet=False)

    # 已初始化时，尝试补齐缺失的默认配置文件
    initializer.initialize(force=False, quiet=quiet, sync_missing=True)
    return True


def reset_config(confirm: bool = False) -> bool:
    """
    重置配置到默认状态

    Args:
        confirm: 确认重置（防止误操作）

    Returns:
        True 表示重置成功
    """
    if not confirm:
        logger.warning("Reset requires confirmation. Pass confirm=True to proceed.")
        return False

    initializer = ConfigInitializer()
    return initializer.initialize(force=True, quiet=False)
