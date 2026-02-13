"""
共享目录管理

管理 ~/.iris/ 全局配置目录
"""

from pathlib import Path


class IrisShareDir:
    """
    管理 ~/.iris/ 共享目录

    目录结构：
    ~/.iris/
    ├── config.toml              # 主配置文件
    ├── .env                     # 全局环境变量
    ├── llm/
    │   └── providers.json       # LLM 提供商配置
    ├── agents/
    │   ├── basic/
    │   │   └── providers.json
    │   └── deep/
    │       ├── subagents.json
    │       ├── mainagents.json
    │       └── middleware/
    ├── tools/
    │   ├── mcp/
    │   │   └── mcp.toml
    │   └── sdk/
    ├── skills/
    ├── sessions/
    └── metadata.json
    """

    _SHARE_DIR_NAME = ".iris"

    # =========================================================================
    # 基础目录
    # =========================================================================

    @classmethod
    def get_share_dir(cls) -> Path:
        """
        获取共享目录路径，不存在则创建
        """
        share_dir = Path.home() / cls._SHARE_DIR_NAME
        share_dir.mkdir(parents=True, exist_ok=True)
        return share_dir

    # =========================================================================
    # 配置文件
    # =========================================================================

    @classmethod
    def get_config_file(cls) -> Path:
        """获取主配置文件路径 (config.toml)"""
        return cls.get_share_dir() / "config.toml"

    @classmethod
    def get_env_file(cls) -> Path:
        """获取全局 .env 文件路径"""
        return cls.get_share_dir() / ".env"

    @classmethod
    def get_metadata_file(cls) -> Path:
        """获取元数据文件路径 (metadata.json)"""
        return cls.get_share_dir() / "metadata.json"

    @classmethod
    def get_global_config_file(cls) -> Path:
        """[兼容] 获取旧版 config.json 路径"""
        return cls.get_share_dir() / "config.json"

    @classmethod
    def get_global_agent_md_file(cls) -> Path:
        """获取全局 agent 指令文件路径"""
        return cls.get_share_dir() / "agent.md"

    # =========================================================================
    # LLM 配置
    # =========================================================================

    @classmethod
    def get_llm_dir(cls) -> Path:
        """获取 LLM 配置目录"""
        llm_dir = cls.get_share_dir() / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)
        return llm_dir

    @classmethod
    def get_providers_file(cls) -> Path:
        """获取 LLM providers 配置文件路径"""
        return cls.get_llm_dir() / "providers.json"

    # =========================================================================
    # Agent 配置
    # =========================================================================

    @classmethod
    def get_agents_dir(cls) -> Path:
        """获取 agents 配置目录"""
        agents_dir = cls.get_share_dir() / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    @classmethod
    def get_basic_agent_dir(cls) -> Path:
        """获取 basic agent 配置目录"""
        basic_dir = cls.get_agents_dir() / "basic"
        basic_dir.mkdir(parents=True, exist_ok=True)
        return basic_dir

    @classmethod
    def get_deep_agent_dir(cls) -> Path:
        """获取 deep agent 配置目录"""
        deep_dir = cls.get_agents_dir() / "deep"
        deep_dir.mkdir(parents=True, exist_ok=True)
        return deep_dir

    @classmethod
    def get_basic_agent_providers_file(cls) -> Path:
        """获取 basic agent providers 配置文件路径"""
        return cls.get_basic_agent_dir() / "providers.json"

    @classmethod
    def get_subagents_file(cls) -> Path:
        """获取 subagents 配置文件路径"""
        return cls.get_deep_agent_dir() / "subagents.json"

    @classmethod
    def get_mainagents_file(cls) -> Path:
        """获取 mainagents 配置文件路径"""
        return cls.get_deep_agent_dir() / "mainagents.json"

    # =========================================================================
    # 工具配置
    # =========================================================================

    @classmethod
    def get_tools_dir(cls) -> Path:
        """获取 tools 配置目录"""
        tools_dir = cls.get_share_dir() / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        return tools_dir

    @classmethod
    def get_mcp_dir(cls) -> Path:
        """获取 MCP 配置目录"""
        mcp_dir = cls.get_tools_dir() / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        return mcp_dir

    @classmethod
    def get_sdk_dir(cls) -> Path:
        """获取 SDK 工具配置目录"""
        sdk_dir = cls.get_tools_dir() / "sdk"
        sdk_dir.mkdir(parents=True, exist_ok=True)
        return sdk_dir

    @classmethod
    def get_mcp_config_file(cls) -> Path:
        """获取 MCP 配置文件路径"""
        return cls.get_mcp_dir() / "mcp.toml"

    # =========================================================================
    # Skills 配置
    # =========================================================================

    @classmethod
    def get_skills_dir(cls) -> Path:
        """获取 skills 配置目录"""
        skills_dir = cls.get_share_dir() / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        return skills_dir

    # =========================================================================
    # 会话存储
    # =========================================================================

    @classmethod
    def get_sessions_dir(cls) -> Path:
        """获取会话存储目录"""
        sessions_dir = cls.get_share_dir() / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        return sessions_dir
