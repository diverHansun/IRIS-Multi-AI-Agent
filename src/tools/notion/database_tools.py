"""
Notion数据库操作工具

提供对Notion数据库的高级操作功能，包括查询、搜索、数据提取等。
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from .client import NotionClient, create_notion_client
from .data_processor import NotionDataProcessor

logger = logging.getLogger(__name__)


class NotionDatabaseTools:
    """Notion数据库操作工具类"""
    
    def __init__(self, client: Optional[NotionClient] = None):
        """
        初始化数据库工具
        
        Args:
            client: Notion客户端，如果不提供则创建默认客户端
        """
        self.client = client or create_notion_client()
        self.processor = NotionDataProcessor()
    
    def _validate_database_id(self, database_id: str) -> str:
        """
        验证并清理数据库ID
        
        Args:
            database_id: 数据库ID
            
        Returns:
            清理后的数据库ID
            
        Raises:
            ValueError: 如果ID格式无效
        """
        if not database_id:
            raise ValueError("数据库ID不能为空")
        
        # 移除可能的URL部分，只保留UUID
        database_id = database_id.strip()
        
        # 如果是完整URL，提取ID部分
        if 'notion.so' in database_id:
            # 匹配Notion URL中的数据库ID
            match = re.search(r'([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', database_id)
            if match:
                database_id = match.group(1)
            else:
                raise ValueError(f"无法从URL中提取有效的数据库ID: {database_id}")
        
        # 移除连字符，统一格式
        clean_id = database_id.replace('-', '')
        
        # 验证是否为32个十六进制字符
        if not re.match(r'^[a-f0-9]{32}$', clean_id, re.IGNORECASE):
            raise ValueError(f"数据库ID格式无效。应为32个十六进制字符，得到: {database_id}")
        
        # 返回带连字符的标准UUID格式
        return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:32]}"
    
    async def get_database_info(self, database_id: str) -> Dict[str, Any]:
        """
        获取数据库基本信息
        
        Args:
            database_id: 数据库ID
            
        Returns:
            数据库信息
        """
        try:
            # 验证并清理数据库ID
            clean_database_id = self._validate_database_id(database_id)
            logger.info(f"获取数据库信息: {clean_database_id}")
            raw_data = await self.client.get_database(clean_database_id)
            
            # 提取基本信息
            info = {
                "id": raw_data.get("id"),
                "title": self.processor.extract_plain_text(raw_data.get("title", [])),
                "description": self.processor.extract_plain_text(raw_data.get("description", [])),
                "created_time": raw_data.get("created_time"),
                "last_edited_time": raw_data.get("last_edited_time"),
                "url": raw_data.get("url"),
                "properties": {}
            }
            
            # 处理属性架构
            properties = raw_data.get("properties", {})
            for prop_name, prop_data in properties.items():
                info["properties"][prop_name] = {
                    "type": prop_data.get("type"),
                    "name": prop_name
                }
                
                # 添加特定类型的额外信息
                prop_type = prop_data.get("type")
                if prop_type == "select":
                    options = prop_data.get("select", {}).get("options", [])
                    info["properties"][prop_name]["options"] = [opt.get("name") for opt in options]
                elif prop_type == "multi_select":
                    options = prop_data.get("multi_select", {}).get("options", [])
                    info["properties"][prop_name]["options"] = [opt.get("name") for opt in options]
                elif prop_type == "formula":
                    expression = prop_data.get("formula", {}).get("expression", "")
                    info["properties"][prop_name]["expression"] = expression
            
            return info
            
        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            raise
    
    async def query_database_simple(
        self, 
        database_id: str, 
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        简单查询数据库（获取所有记录）
        
        Args:
            database_id: 数据库ID
            limit: 限制返回记录数
            
        Returns:
            查询结果
        """
        try:
            clean_database_id = self._validate_database_id(database_id)
            logger.info(f"简单查询数据库: {clean_database_id}")
            
            page_size = min(limit or 100, 100)
            raw_result = await self.client.query_database(
                database_id=clean_database_id,
                page_size=page_size
            )
            
            return self.processor.process_database_query_result(raw_result)
            
        except Exception as e:
            logger.error(f"查询数据库失败: {e}")
            raise
    
    async def query_database_with_filter(
        self,
        database_id: str,
        property_name: str,
        filter_type: str,
        filter_value: Any,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        带过滤条件查询数据库
        
        Args:
            database_id: 数据库ID
            property_name: 要过滤的属性名
            filter_type: 过滤类型（equals, contains, starts_with等）
            filter_value: 过滤值
            limit: 限制返回记录数
            
        Returns:
            查询结果
        """
        try:
            clean_database_id = self._validate_database_id(database_id)
            logger.info(f"条件查询数据库: {clean_database_id}, 条件: {property_name} {filter_type} {filter_value}")
            
            # 构建过滤条件
            filter_condition = {
                "property": property_name,
                "rich_text": {filter_type: filter_value}
            }
            
            # 如果是其他类型的属性，需要调整过滤条件结构
            if filter_type in ["equals", "does_not_equal"]:
                if isinstance(filter_value, bool):
                    filter_condition = {
                        "property": property_name,
                        "checkbox": {filter_type: filter_value}
                    }
                elif isinstance(filter_value, (int, float)):
                    filter_condition = {
                        "property": property_name,
                        "number": {filter_type: filter_value}
                    }
            
            page_size = min(limit or 100, 100)
            raw_result = await self.client.query_database(
                database_id=clean_database_id,
                filter_conditions=filter_condition,
                page_size=page_size
            )
            
            return self.processor.process_database_query_result(raw_result)
            
        except Exception as e:
            logger.error(f"条件查询数据库失败: {e}")
            raise
    
    async def search_database_content(
        self,
        database_id: str,
        search_text: str,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        搜索数据库内容
        
        Args:
            database_id: 数据库ID
            search_text: 搜索文本
            limit: 限制返回记录数
            
        Returns:
            搜索结果
        """
        try:
            clean_database_id = self._validate_database_id(database_id)
            logger.info(f"搜索数据库内容: {clean_database_id}, 搜索词: {search_text}")
            
            # 构建搜索过滤条件
            filter_condition = {
                "and": [
                    {
                        "property": "object",
                        "rich_text": {"equals": "page"}
                    },
                    {
                        "or": [
                            {
                                "property": "parent",
                                "relation": {"contains": clean_database_id}
                            }
                        ]
                    }
                ]
            }
            
            page_size = min(limit or 100, 100)
            raw_result = await self.client.search(
                query=search_text,
                filter_conditions=filter_condition,
                page_size=page_size
            )
            
            return self.processor.process_search_result(raw_result)
            
        except Exception as e:
            logger.error(f"搜索数据库内容失败: {e}")
            raise
    
    async def get_database_records_summary(self, database_id: str) -> str:
        """
        获取数据库记录摘要
        
        Args:
            database_id: 数据库ID
            
        Returns:
            数据库摘要文本
        """
        try:
            clean_database_id = self._validate_database_id(database_id)
            # 获取数据库信息
            db_info = await self.get_database_info(clean_database_id)
            
            # 获取部分记录
            query_result = await self.query_database_simple(clean_database_id, limit=10)
            
            # 构建摘要
            summary_parts = [
                f"数据库: {db_info['title']}",
                f"描述: {db_info.get('description', '无')}"
            ]
            
            if db_info['properties']:
                prop_names = list(db_info['properties'].keys())
                summary_parts.append(f"属性字段: {', '.join(prop_names[:5])}")
                if len(prop_names) > 5:
                    summary_parts.append(f"（还有{len(prop_names) - 5}个字段）")
            
            records = query_result['results']
            summary_parts.append(f"记录数量: {len(records)}+")
            
            if records:
                summary_parts.append("\\n最近记录示例:")
                for i, record in enumerate(records[:3]):
                    props = record['properties']
                    title = None
                    
                    # 找到标题字段
                    for prop_name, prop_value in props.items():
                        if prop_value and isinstance(prop_value, str) and prop_value.strip():
                            title = prop_value[:50]
                            break
                    
                    if title:
                        summary_parts.append(f"{i+1}. {title}")
            
            return "\\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"获取数据库摘要失败: {e}")
            return f"获取数据库摘要时出错: {str(e)}"
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.close()


# 同步包装函数，用于LangChain工具集成
def sync_get_database_info(database_id: str) -> Dict[str, Any]:
    """同步获取数据库信息"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionDatabaseTools()
            try:
                return await tools.get_database_info(database_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_query_database_simple(database_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """同步简单查询数据库"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionDatabaseTools()
            try:
                return await tools.query_database_simple(database_id, limit)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_search_database_content(
    database_id: str, 
    search_text: str, 
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """同步搜索数据库内容"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionDatabaseTools()
            try:
                return await tools.search_database_content(database_id, search_text, limit)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)


def sync_get_database_summary(database_id: str) -> str:
    """同步获取数据库摘要"""
    from .sync_utils import run_async_safely
    
    def _async_wrapper():
        async def _inner():
            tools = NotionDatabaseTools()
            try:
                return await tools.get_database_records_summary(database_id)
            finally:
                await tools.close()
        return _inner()
    
    return run_async_safely(_async_wrapper)
