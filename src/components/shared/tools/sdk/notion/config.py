"""
Notion API配置模块

管理Notion API的配置信息，包括认证token、API版本等。
"""

import os
from typing import Optional


class NotionConfig:
    """Notion API配置类"""
    
    # Notion API相关配置
    API_BASE_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化Notion配置
        
        Args:
            token: Notion Integration Token，如果不提供则从环境变量读取
        """
        self.token = token or self._get_token_from_env()
        
        if not self.token:
            raise ValueError(
                "Notion token未提供。请设置NOTION_TOKEN环境变量或传入token参数。\n"
                "获取token的步骤：\n"
                "1. 访问 https://www.notion.so/my-integrations\n"
                "2. 创建新的Integration\n" 
                "3. 复制Internal Integration Token\n"
                "4. 设置环境变量：NOTION_TOKEN=your_token"
            )
    
    def _get_token_from_env(self) -> Optional[str]:
        """从环境变量获取token"""
        return os.getenv("NOTION_TOKEN")
    
    @property
    def headers(self) -> dict:
        """获取API请求头"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": self.API_VERSION
        }
    
    def validate_config(self) -> bool:
        """验证配置是否有效"""
        return bool(self.token and len(self.token.strip()) > 0)


# 默认配置实例
_default_config = None


def get_default_config() -> NotionConfig:
    """获取默认配置实例（单例模式）"""
    global _default_config
    if _default_config is None:
        _default_config = NotionConfig()
    return _default_config


def set_default_config(config: NotionConfig) -> None:
    """设置默认配置实例"""
    global _default_config
    _default_config = config

