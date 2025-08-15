"""
Notion LangChain工具集成

将Notion功能集成到LangChain工具系统中，提供给AI Agent使用。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .database_tools import (
    sync_get_database_info,
    sync_query_database_simple,
    sync_search_database_content,
    sync_get_database_summary
)
from .page_tools import (
    sync_get_page_info,
    sync_get_page_content,
    sync_get_page_full_content,
    sync_get_page_summary,
    sync_search_page_content
)
# 搜索工具的导入在后面动态导入以避免循环导入

logger = logging.getLogger(__name__)


# 输入模型定义
class DatabaseInfoInput(BaseModel):
    """获取数据库信息的输入模型"""
    database_id: str = Field(description="Notion数据库ID")


class DatabaseQueryInput(BaseModel):
    """查询数据库的输入模型"""
    database_id: str = Field(description="Notion数据库ID")
    limit: Optional[int] = Field(default=10, description="限制返回记录数，默认10，最大100")


class DatabaseSearchInput(BaseModel):
    """搜索数据库内容的输入模型"""
    database_id: str = Field(description="Notion数据库ID")
    search_text: str = Field(description="搜索关键词")
    limit: Optional[int] = Field(default=10, description="限制返回记录数，默认10，最大100")


class PageInfoInput(BaseModel):
    """获取页面信息的输入模型"""
    page_id: str = Field(description="Notion页面ID")


class PageSearchInput(BaseModel):
    """搜索页面内容的输入模型"""
    page_id: str = Field(description="Notion页面ID")
    search_text: str = Field(description="搜索关键词")


class NotionSearchInput(BaseModel):
    """搜索Notion内容的输入模型"""
    query: str = Field(description="搜索查询")
    limit: Optional[int] = Field(default=10, description="限制返回结果数，默认10，最大100")


# LangChain工具类定义
class NotionGetDatabaseInfoTool(BaseTool):
    """获取Notion数据库信息工具"""
    name: str = "notion_get_database_info"
    description: str = "获取Notion数据库的基本信息，包括标题、描述、属性架构等"
    args_schema: type = DatabaseInfoInput
    
    def _run(self, database_id: str) -> str:
        try:
            result = sync_get_database_info(database_id)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            return f"错误: {str(e)}"


class NotionQueryDatabaseTool(BaseTool):
    """查询Notion数据库工具"""
    name: str = "notion_query_database"
    description: str = "查询Notion数据库中的记录，返回结构化数据"
    args_schema: type = DatabaseQueryInput
    
    def _run(self, database_id: str, limit: Optional[int] = 10) -> str:
        try:
            result = sync_query_database_simple(database_id, limit)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"查询数据库失败: {e}")
            return f"错误: {str(e)}"


class NotionGetDatabaseSummaryTool(BaseTool):
    """获取Notion数据库摘要工具"""
    name: str = "notion_get_database_summary"
    description: str = "获取Notion数据库的简洁摘要，包括基本信息和部分记录示例"
    args_schema: type = DatabaseInfoInput
    
    def _run(self, database_id: str) -> str:
        try:
            return sync_get_database_summary(database_id)
        except Exception as e:
            logger.error(f"获取数据库摘要失败: {e}")
            return f"错误: {str(e)}"


class NotionGetPageInfoTool(BaseTool):
    """获取Notion页面信息工具"""
    name: str = "notion_get_page_info"
    description: str = "获取Notion页面的基本信息和属性"
    args_schema: type = PageInfoInput
    
    def _run(self, page_id: str) -> str:
        try:
            result = sync_get_page_info(page_id)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取页面信息失败: {e}")
            return f"错误: {str(e)}"


class NotionGetPageContentTool(BaseTool):
    """获取Notion页面内容工具"""
    name: str = "notion_get_page_content"
    description: str = "获取Notion页面的详细内容，包括所有文本块"
    args_schema: type = PageInfoInput
    
    def _run(self, page_id: str) -> str:
        try:
            result = sync_get_page_content(page_id)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"获取页面内容失败: {e}")
            return f"错误: {str(e)}"


class NotionGetPageSummaryTool(BaseTool):
    """获取Notion页面摘要工具"""
    name: str = "notion_get_page_summary"
    description: str = "获取Notion页面的简洁摘要，包括标题、属性和内容预览"
    args_schema: type = PageInfoInput
    
    def _run(self, page_id: str) -> str:
        try:
            return sync_get_page_summary(page_id)
        except Exception as e:
            logger.error(f"获取页面摘要失败: {e}")
            return f"错误: {str(e)}"


class NotionSearchPageContentTool(BaseTool):
    """搜索Notion页面内容工具"""
    name: str = "notion_search_page_content"
    description: str = "在指定Notion页面内容中搜索关键词"
    args_schema: type = PageSearchInput
    
    def _run(self, page_id: str, search_text: str) -> str:
        try:
            result = sync_search_page_content(page_id, search_text)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"搜索页面内容失败: {e}")
            return f"错误: {str(e)}"


class NotionSearchTool(BaseTool):
    """Notion智能搜索工具"""
    name: str = "notion_search"
    description: str = "在Notion工作区中智能搜索页面和数据库，支持精确匹配和模糊搜索"
    args_schema: type = NotionSearchInput
    
    def _run(self, query: str, limit: Optional[int] = 10) -> str:
        try:
            from .search_tools import sync_search_notion_smart
            result = sync_search_notion_smart(query, limit)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"智能搜索Notion失败: {e}")
            # 降级到标准搜索
            try:
                from .search_tools import sync_search_notion
                result = sync_search_notion(query, limit)
                return json.dumps(result, ensure_ascii=False, indent=2)
            except Exception as e2:
                return f"错误: {str(e2)}"


class NotionSearchDatabasesTool(BaseTool):
    """搜索Notion数据库工具"""
    name: str = "notion_search_databases"
    description: str = "专门搜索Notion工作区中的数据库"
    args_schema: type = NotionSearchInput
    
    def _run(self, query: str, limit: Optional[int] = 10) -> str:
        try:
            from .search_tools import sync_search_databases
            result = sync_search_databases(query, limit)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"搜索数据库失败: {e}")
            return f"错误: {str(e)}"


class NotionSearchPagesTool(BaseTool):
    """搜索Notion页面工具"""
    name: str = "notion_search_pages"
    description: str = "专门搜索Notion工作区中的页面"
    args_schema: type = NotionSearchInput
    
    def _run(self, query: str, limit: Optional[int] = 10) -> str:
        try:
            from .search_tools import sync_search_pages
            result = sync_search_pages(query, limit)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"搜索页面失败: {e}")
            return f"错误: {str(e)}"


# 工具实例化
def get_notion_database_tools() -> List[BaseTool]:
    """获取Notion数据库相关工具"""
    return [
        NotionGetDatabaseInfoTool(),
        NotionQueryDatabaseTool(),
        NotionGetDatabaseSummaryTool(),
    ]


def get_notion_page_tools() -> List[BaseTool]:
    """获取Notion页面相关工具"""
    return [
        NotionGetPageInfoTool(),
        NotionGetPageContentTool(),
        NotionGetPageSummaryTool(),
        NotionSearchPageContentTool(),
    ]


def get_notion_search_tools() -> List[BaseTool]:
    """获取Notion搜索相关工具"""
    return [
        NotionSearchTool(),
        NotionSearchDatabasesTool(),
        NotionSearchPagesTool(),
    ]


def get_all_notion_tools() -> List[BaseTool]:
    """获取所有Notion工具"""
    tools = []
    tools.extend(get_notion_database_tools())
    tools.extend(get_notion_page_tools())
    tools.extend(get_notion_search_tools())
    return tools


# 主要导出函数
def get_notion_tools() -> List[BaseTool]:
    """
    获取可用的Notion工具列表
    
    Returns:
        Notion工具列表
    """
    return get_all_notion_tools()


# 工具描述
NOTION_TOOLS_DESCRIPTION = """
Notion工具集提供以下功能：

数据库操作:
- notion_get_database_info: 获取数据库信息和架构
- notion_query_database: 查询数据库记录
- notion_get_database_summary: 获取数据库摘要

页面操作:
- notion_get_page_info: 获取页面基本信息
- notion_get_page_content: 获取页面详细内容
- notion_get_page_summary: 获取页面摘要
- notion_search_page_content: 搜索页面内容

搜索功能:
- notion_search: 全局搜索
- notion_search_databases: 搜索数据库
- notion_search_pages: 搜索页面

使用前请确保设置了NOTION_TOKEN环境变量。
"""
