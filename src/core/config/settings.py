"""
应用设置模块（增强版）

管理环境变量和应用配置，支持从 ConfigLoader 读取配置
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    应用设置类

    从环境变量读取配置，保持向后兼容
    """

    # 智谱AI API 配置
    zhipu_api_key: str = os.getenv("ZHIPU_API_KEY") or ""

    # OpenAI API 配置
    openai_api_key: str = os.getenv("OPENAI_API_KEY") or ""
    openai_base_url: str = os.getenv("OPENAI_BASE_URL") or ""

    # Anthropic API 配置
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY") or ""

    # 通义千问 API 配置
    tongyi_api_key: str = os.getenv("TONGYI_API_KEY") or ""

    # Ollama API 配置
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))
    ollama_keep_alive: str = os.getenv("OLLAMA_KEEP_ALIVE") or "5m"
    default_ollama_model: str = os.getenv("DEFAULT_OLLAMA_MODEL") or "gpt-oss:20b"

    # Tavily Search API 配置
    tavily_api_key: str = os.getenv("TAVILY_API_KEY") or ""

    # 高德地图 API 配置
    amap_api_key: str = os.getenv("AMAP_API_KEY") or ""

    # Notion API 配置
    notion_token: str = os.getenv("NOTION_TOKEN") or ""

    # 默认LLM配置
    default_llm_provider: str = os.getenv("DEFAULT_LLM_PROVIDER") or "zhipu"
    default_llm_model: str = os.getenv("DEFAULT_LLM_MODEL") or ""

    # 流式输出配置
    enable_streaming_by_default: bool = (
        os.getenv("ENABLE_STREAMING_BY_DEFAULT", "false").lower() == "true"
    )
    streaming_display_refresh_rate: int = int(
        os.getenv("STREAMING_DISPLAY_REFRESH_RATE", "10")
    )
    streaming_delay_ms: int = int(os.getenv("STREAMING_DELAY_MS", "50"))

    class Config:
        env_file = None  # 禁用自动读取.env文件，我们手动处理

    # =========================================================================
    # 便捷方法
    # =========================================================================

    def has_zhipu(self) -> bool:
        """检查是否配置了智谱 API"""
        return bool(self.zhipu_api_key) and not self.zhipu_api_key.startswith("your_")

    def has_openai(self) -> bool:
        """检查是否配置了 OpenAI API"""
        return bool(self.openai_api_key) and not self.openai_api_key.startswith("your_")

    def has_anthropic(self) -> bool:
        """检查是否配置了 Anthropic API"""
        return bool(self.anthropic_api_key) and not self.anthropic_api_key.startswith(
            "your_"
        )

    def has_tongyi(self) -> bool:
        """检查是否配置了通义千问 API"""
        return bool(self.tongyi_api_key) and not self.tongyi_api_key.startswith("your_")

    def has_tavily(self) -> bool:
        """检查是否配置了 Tavily API"""
        return bool(self.tavily_api_key) and not self.tavily_api_key.startswith("your_")

    def has_amap(self) -> bool:
        """检查是否配置了高德地图 API"""
        return bool(self.amap_api_key) and not self.amap_api_key.startswith("your_")

    def has_notion(self) -> bool:
        """检查是否配置了 Notion API"""
        return (
            bool(self.notion_token)
            and not self.notion_token.startswith("your_")
            and not self.notion_token.startswith("secret_")
        )

    def get_api_key(self, provider: str) -> Optional[str]:
        """获取指定提供商的 API key"""
        provider_lower = provider.lower()
        key_mapping = {
            "zhipu": self.zhipu_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "tongyi": self.tongyi_api_key,
            "tavily": self.tavily_api_key,
            "amap": self.amap_api_key,
            "notion": self.notion_token,
        }
        return key_mapping.get(provider_lower)

    def has_api_key(self, provider: str) -> bool:
        """检查是否配置了指定提供商的 API key"""
        check_methods = {
            "zhipu": self.has_zhipu,
            "openai": self.has_openai,
            "anthropic": self.has_anthropic,
            "tongyi": self.has_tongyi,
            "tavily": self.has_tavily,
            "amap": self.has_amap,
            "notion": self.has_notion,
        }
        method = check_methods.get(provider.lower())
        return method() if method else False


# 全局设置实例
settings = Settings()


def _validate_config() -> None:
    """验证配置信息 - 检查必需的配置项"""
    errors = []

    # 1. 检查必需的LLM配置（至少一个）
    has_zhipu = settings.has_zhipu()
    has_openai = settings.has_openai()
    has_anthropic = settings.has_anthropic()
    has_ollama = True  # Ollama 通常本地运行，无需密钥

    if not has_zhipu and not has_openai and not has_anthropic:
        errors.append(
            "At least one LLM API key must be configured "
            "(ZHIPU_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
        )

    # 2. 记录可选配置状态（仅在 DEBUG 级别）
    logger.debug(
        "LLM Providers: zhipu=%s, openai=%s, anthropic=%s, ollama=%s",
        has_zhipu,
        has_openai,
        has_anthropic,
        has_ollama,
    )
    logger.debug(
        "Optional services: tavily=%s, amap=%s, notion=%s",
        settings.has_tavily(),
        settings.has_amap(),
        settings.has_notion(),
    )

    # 3. 输出错误信息
    if errors:
        for error in errors:
            logger.warning(error)
        logger.warning("Please configure your API keys in ~/.iris/.env or project .env file")


def reload_settings() -> Settings:
    """
    重新加载设置

    用于在运行时更新环境变量后刷新设置
    """
    global settings
    settings = Settings()
    _validate_config()
    return settings


# 自动验证配置信息
_validate_config()
