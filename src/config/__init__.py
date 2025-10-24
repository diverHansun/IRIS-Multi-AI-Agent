"""
配置管理模块

处理环境变量和应用配置加载
"""

# 首先加载环境变量（必须在其他导入之前）
from .env_loader import safe_load_dotenv

# 然后导入设置
from .settings import settings, Settings

__all__ = [
    # 环境变量加载
    "safe_load_dotenv",
    # 设置
    "settings",
    "Settings",
]
