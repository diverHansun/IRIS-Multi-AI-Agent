"""
配置数据模型

使用 Pydantic 定义配置结构，支持 SecretStr 安全存储敏感信息
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, SecretStr, field_serializer, model_validator


class APIKeysConfig(BaseModel):
    """API 密钥配置"""

    zhipu_api_key: Optional[SecretStr] = None
    openai_api_key: Optional[SecretStr] = None
    anthropic_api_key: Optional[SecretStr] = None
    tongyi_api_key: Optional[SecretStr] = None
    tavily_api_key: Optional[SecretStr] = None
    amap_api_key: Optional[SecretStr] = None
    notion_token: Optional[SecretStr] = None

    @field_serializer("*", when_used="json")
    def serialize_secrets(self, v: Optional[SecretStr]) -> Optional[str]:
        """序列化时使用环境变量引用格式，保护实际值"""
        if v is None:
            return None
        # 返回引用格式而非实际值
        return "${ENV_VAR}"

    def get_key(self, provider: str) -> Optional[str]:
        """获取指定提供商的 API key"""
        key_mapping = {
            "zhipu": self.zhipu_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "tongyi": self.tongyi_api_key,
            "tavily": self.tavily_api_key,
            "amap": self.amap_api_key,
            "notion": self.notion_token,
        }
        secret = key_mapping.get(provider.lower())
        if secret:
            return secret.get_secret_value()
        return None

    def has_key(self, provider: str) -> bool:
        """检查是否配置了指定提供商的 API key"""
        key = self.get_key(provider)
        return key is not None and len(key) > 0 and not key.startswith("your_")


class DefaultsConfig(BaseModel):
    """默认设置配置"""

    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.5-flash"
    agent_type: str = "basic"  # basic, deep
    streaming: bool = True
    temperature: float = 0.6


class DisplayConfig(BaseModel):
    """显示配置"""

    show_welcome: bool = True
    enable_colors: bool = True
    streaming_refresh_rate: int = 10
    streaming_delay_ms: int = 50


class MCPConfig(BaseModel):
    """MCP 配置"""

    enabled: bool = True
    auto_start: bool = True
    config_file: str = "tools/mcp/mcp.toml"
    tool_call_timeout_ms: int = 60000


class DeepAgentConfig(BaseModel):
    """Deep Agent 配置"""

    default_provider: str = "anthropic"
    default_model: str = "claude-4.5-sonnet"
    max_execution_time: int = 900
    recursion_limit: int = 300


class OllamaConfig(BaseModel):
    """Ollama 配置"""

    base_url: str = "http://localhost:11434"
    timeout: int = 60
    keep_alive: str = "5m"
    default_model: str = "gpt-oss:20b"


class PathsConfig(BaseModel):
    """配置文件路径（相对于 ~/.iris/）"""

    llm_providers: str = "llm/providers.json"
    basic_agent_providers: str = "agents/basic/providers.json"
    deep_agent_subagents: str = "agents/deep/subagents.json"
    deep_agent_mainagents: str = "agents/deep/mainagents.json"
    mcp_config: str = "tools/mcp/mcp.toml"


class IrisConfig(BaseModel):
    """IRIS 主配置结构"""

    schema_version: str = "1.0"
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    deep_agent: DeepAgentConfig = Field(default_factory=DeepAgentConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # 内部标记（不序列化）
    _source_path: Optional[Path] = None
    _is_user_config: bool = False
    _is_project_config: bool = False

    @model_validator(mode="after")
    def validate_config(self) -> "IrisConfig":
        """验证配置有效性"""
        # 验证 schema_version
        if not self.schema_version:
            self.schema_version = "1.0"
        return self

    def get_api_key(self, provider: str) -> Optional[str]:
        """获取指定提供商的 API key（便捷方法）"""
        return self.api_keys.get_key(provider)

    def has_api_key(self, provider: str) -> bool:
        """检查是否配置了指定提供商的 API key（便捷方法）"""
        return self.api_keys.has_key(provider)
