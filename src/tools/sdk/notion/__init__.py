"""
Notion工具模块

提供与Notion API集成的完整工具套件，支持数据库查询、页面读取、搜索等功能。
设计遵循高内聚低耦合原则，便于维护和扩展。

主要组件:
- NotionClient: Notion API客户端封装
- NotionConfig: 配置管理
- NotionDataProcessor: 数据处理器
- NotionDatabaseTools: 数据库操作工具
- NotionPageTools: 页面操作工具
- NotionSearchTools: 搜索工具
- LangChain集成: 与LangChain框架集成的工具

使用方法:
1. 设置环境变量 NOTION_TOKEN
2. 导入并使用相应的工具类
3. 或者直接使用 get_available_notion_tools() 获取LangChain工具列表

示例:
    from src.tools.notion import get_available_notion_tools
    
    tools = get_available_notion_tools()
    # 在LangChain Agent中使用这些工具
"""

from .config import NotionConfig, get_default_config, set_default_config
from .client import NotionClient, create_notion_client, NotionAPIError
from .data_processor import NotionDataProcessor
from .database_tools import NotionDatabaseTools
from .page_tools import NotionPageTools
from .search_tools import NotionSearchTools
from .adapter import (
    get_available_notion_tools,
    get_notion_database_tools,
    get_notion_page_tools,
    get_notion_search_tools,
    get_all_notion_tools,
    NOTION_TOOLS_DESCRIPTION
)

__version__ = "1.0.0"
__author__ = "Agent Demo"

# 主要导出的类和函数
__all__ = [
    # 配置
    "NotionConfig",
    "get_default_config",
    "set_default_config",
    
    # 客户端
    "NotionClient",
    "create_notion_client",
    "NotionAPIError",
    
    # 数据处理
    "NotionDataProcessor",
    
    # 工具类
    "NotionDatabaseTools",
    "NotionPageTools", 
    "NotionSearchTools",
    
    # LangChain集成
    "get_available_notion_tools",
    "get_notion_database_tools",
    "get_notion_page_tools",
    "get_notion_search_tools",
    "get_all_notion_tools",
    "NOTION_TOOLS_DESCRIPTION",
    
    # 辅助函数
    "check_configuration",
    "is_auth_configured",
    "ensure_tools_initialized",
]

# 模块级别的常量
MODULE_DESCRIPTION = """
Notion工具模块提供完整的Notion API集成功能：

🗃️ 数据库操作:
  - 获取数据库信息和架构
  - 查询数据库记录
  - 条件过滤和搜索

📄 页面操作:
  - 读取页面信息和属性
  - 获取页面内容（包括嵌套块）
  - 页面内容搜索

🔍 搜索功能:
  - 全局工作区搜索
  - 专门的数据库/页面搜索
  - 智能搜索结果处理

🔧 技术特性:
  - 异步API调用优化性能
  - 完整的错误处理和日志记录
  - 模块化设计便于维护
  - LangChain框架深度集成

📋 使用要求:
  - 需要设置NOTION_TOKEN环境变量
  - 确保Notion Integration有相应权限
  - 支持Python 3.7+

获取详细使用说明请查看各模块的文档字符串。
"""


def get_module_info() -> dict:
    """
    获取模块信息
    
    Returns:
        包含模块版本、描述等信息的字典
    """
    return {
        "name": "notion",
        "version": __version__,
        "author": __author__,
        "description": MODULE_DESCRIPTION,
        "tools_count": len(get_available_notion_tools()),
        "components": [
            "NotionClient",
            "NotionDatabaseTools", 
            "NotionPageTools",
            "NotionSearchTools",
            "LangChain Integration"
        ]
    }


def check_configuration() -> dict:
    """
    检查模块配置状态
    
    Returns:
        配置状态信息
    """
    try:
        config = get_default_config()
        is_configured = config.validate_config()
        
        return {
            "configured": is_configured,
            "token_available": bool(config.token),
            "api_version": config.API_VERSION,
            "base_url": config.API_BASE_URL
        }
    except Exception as e:
        return {
            "configured": False,
            "error": str(e),
            "token_available": False
        }


def is_auth_configured() -> bool:
    """
    检查Notion认证是否已配置
    
    Returns:
        bool: 如果认证已配置返回True，否则返回False
    """
    try:
        config = get_default_config()
        return config.validate_config()
    except Exception:
        return False


async def ensure_tools_initialized():
    """
    确保工具已初始化
    
    Returns:
        工具列表或None
    """
    try:
        if not is_auth_configured():
            return None
        
        tools = get_available_notion_tools()
        return tools
    except Exception:
        return None
