"""
应用设置模块

管理环境变量和应用配置
"""

from pydantic_settings import BaseSettings
import os
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用设置类"""
    # 智谱AI API 配置
    zhipu_api_key: str = os.getenv("ZHIPU_API_KEY") or ""

    # OpenAI API 配置
    openai_api_key: str = os.getenv("OPENAI_API_KEY") or ""
    openai_base_url: str = os.getenv("OPENAI_BASE_URL") or ""

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
    enable_streaming_by_default: bool = os.getenv("ENABLE_STREAMING_BY_DEFAULT", "false").lower() == "true"
    streaming_display_refresh_rate: int = int(os.getenv("STREAMING_DISPLAY_REFRESH_RATE", "10"))
    streaming_delay_ms: int = int(os.getenv("STREAMING_DELAY_MS", "50"))

    class Config:
        env_file = None  # 禁用自动读取.env文件，我们手动处理


# 全局设置实例
settings = Settings()


# 检查API密钥并记录配置信息
def _validate_config():
    """验证配置信息 - 检查必需的配置项"""
    errors = []
    warnings = []

    # 1. 检查必需的LLM配置（至少一个）
    has_zhipu = settings.zhipu_api_key and not settings.zhipu_api_key.startswith("your_")
    has_openai = settings.openai_api_key and not settings.openai_api_key.startswith("your_")
    has_ollama = True  # Ollama 通常本地运行，无需密钥

    if not has_zhipu and not has_openai:
        errors.append("At least one LLM API key must be configured (ZHIPU_API_KEY or OPENAI_API_KEY)")

    # 2. 检查可选功能的配置
    has_tavily = settings.tavily_api_key and not settings.tavily_api_key.startswith("your_")
    has_amap = settings.amap_api_key and not settings.amap_api_key.startswith("your_")
    has_notion = settings.notion_token and not settings.notion_token.startswith("your_") and not settings.notion_token.startswith("secret_")

    # 3. 记录可选配置状态（仅在 DEBUG 级别）
    logger.debug(f"LLM Providers: zhipu={has_zhipu}, openai={has_openai}, ollama={has_ollama}")
    logger.debug(f"Optional services: tavily={has_tavily}, amap={has_amap}, notion={has_notion}")

    # 4. 输出错误信息
    if errors:
        for error in errors:
            logger.error(error)
        logger.error("Please configure your API keys in .env file")


# 自动验证配置信息
_validate_config()
