"""
配置管理模块

处理环境变量和应用配置。
"""

from dotenv import load_dotenv, find_dotenv
from pydantic_settings import BaseSettings
import os

# 移除硬编码API密钥，改用环境变量

def safe_load_dotenv():
    """安全加载.env文件，自动处理编码问题"""
    env_path = find_dotenv()
    if not env_path:
        print("WARNING: .env file not found, using environment variables")
        return
    
    encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gbk', 'gb2312']
    
    for encoding in encodings:
        try:
            load_dotenv(env_path, encoding=encoding)
            print(f"SUCCESS: .env file loaded with encoding: {encoding}")
            return
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    
    print("WARNING: Could not read .env file, using environment variables or defaults")

# 加载环境变量
safe_load_dotenv()

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

# 检查API密钥
if not settings.zhipu_api_key:
    print("ERROR: ZHIPU_API_KEY not found")
    print("HINT: Please set your ZhipuAI API key in .env file")
    print("HINT: Ensure .env file is saved with UTF-8 encoding") 
else:
    print(f"SUCCESS: ZhipuAI API key configured: {settings.zhipu_api_key[:10]}...{settings.zhipu_api_key[-10:]}") 

# 检查Tavily API密钥
if not settings.tavily_api_key:
    print("WARNING: TAVILY_API_KEY not found")
    print("HINT: Please set your Tavily API key in .env file for enhanced search functionality")
else:
    print(f"SUCCESS: Tavily API key configured: {settings.tavily_api_key[:10]}...{settings.tavily_api_key[-10:]}") 

# 检查OpenAI API密钥
if not settings.openai_api_key:
    print("WARNING: OPENAI_API_KEY not found")
    print("HINT: Please set your OpenAI API key in .env file for GPT models")
else:
    try:
        print(f"SUCCESS: OpenAI API key configured: {settings.openai_api_key[:10]}...{settings.openai_api_key[-10:]}")
    except UnicodeEncodeError:
        print("SUCCESS: OpenAI API key configured (length: {} chars)".format(len(settings.openai_api_key)))

# 检查高德地图API密钥
if not settings.amap_api_key:
    print("WARNING: AMAP_API_KEY not found")
    print("HINT: Please set your Amap API key in .env file for map search functionality")
else:
    print(f"SUCCESS: Amap API key configured: {settings.amap_api_key[:10]}...{settings.amap_api_key[-10:]}") 

# 检查 Notion API 密钥
if not settings.notion_token:
    print("WARNING: NOTION_TOKEN not found")
    print("HINT: Please set your Notion integration token in .env file for Notion functionality")
else:
    print(f"SUCCESS: Notion token configured: {settings.notion_token[:10]}...{settings.notion_token[-10:]}")

# 显示LLM配置信息
available_llms = []
if settings.zhipu_api_key:
    available_llms.append("zhipu")
if settings.openai_api_key:
    available_llms.append("openai")
# Ollama 不需要API密钥，始终可用
available_llms.append("ollama")

if available_llms:
    print(f"SUCCESS: Available LLM providers: {', '.join(available_llms)}")
    print(f"INFO: Default LLM provider: {settings.default_llm_provider}")
else:
    print("ERROR: No LLM providers configured!")
    print("HINT: Please set at least one of ZHIPU_API_KEY or OPENAI_API_KEY")