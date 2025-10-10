"""
Notion API客户端模块

提供与Notion API交互的核心功能，包括数据库查询、页面读取等。
采用异步设计以提高性能。
"""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import json
from datetime import datetime

from .config import NotionConfig, get_default_config

logger = logging.getLogger(__name__)


class NotionAPIError(Exception):
    """Notion API错误基类"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class NotionClient:
    """
    Notion API客户端
    
    提供对Notion API的封装，支持数据库查询、页面读取等功能。
    """
    
    def __init__(self, config: Optional[NotionConfig] = None):
        """
        初始化Notion客户端
        
        Args:
            config: Notion配置，如果不提供则使用默认配置
        """
        self.config = config or get_default_config()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.config.headers,
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session
    
    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """
        发送HTTP请求到Notion API
        
        Args:
            method: HTTP方法
            endpoint: API端点
            data: 请求体数据
            params: URL参数
            
        Returns:
            API响应数据
            
        Raises:
            NotionAPIError: API请求失败时抛出
        """
        session = await self._get_session()
        url = f"{self.config.API_BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params
            ) as response:
                response_data = await response.json()
                
                if not response.ok:
                    error_msg = f"Notion API错误: {response.status}"
                    if response_data and "message" in response_data:
                        error_msg += f" - {response_data['message']}"
                    
                    # 添加更详细的错误信息
                    if response.status == 400:
                        error_msg += "\n可能的原因: 请求参数无效或数据库ID格式错误"
                    elif response.status == 401:
                        error_msg += "\n可能的原因: API Token无效或已过期"
                    elif response.status == 403:
                        error_msg += "\n可能的原因: 没有访问权限，请检查Integration是否已分享给该页面/数据库"
                    elif response.status == 404:
                        error_msg += "\n可能的原因: 数据库/页面不存在或没有访问权限"
                    elif response.status == 429:
                        error_msg += "\n可能的原因: API请求频率超限，请稍后重试"
                    
                    logger.error(f"API请求失败: {error_msg}, URL: {url}")
                    logger.error(f"响应数据: {response_data}")
                    raise NotionAPIError(error_msg, response.status, response_data)
                
                logger.debug(f"API请求成功: {method} {url}")
                return response_data
                
        except aiohttp.ClientError as e:
            error_msg = f"网络请求失败: {str(e)}"
            logger.error(error_msg)
            raise NotionAPIError(error_msg)
    
    async def get_database(self, database_id: str) -> dict:
        """
        获取数据库信息
        
        Args:
            database_id: 数据库ID
            
        Returns:
            数据库信息
        """
        logger.info(f"获取数据库信息: {database_id}")
        return await self._make_request("GET", f"databases/{database_id}")
    
    async def query_database(
        self, 
        database_id: str, 
        filter_conditions: Optional[dict] = None,
        sorts: Optional[List[dict]] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> dict:
        """
        查询数据库内容
        
        Args:
            database_id: 数据库ID
            filter_conditions: 过滤条件
            sorts: 排序条件
            start_cursor: 分页游标
            page_size: 页面大小（最大100）
            
        Returns:
            查询结果
        """
        logger.info(f"查询数据库: {database_id}")
        
        data = {}
        if filter_conditions:
            data["filter"] = filter_conditions
        if sorts:
            data["sorts"] = sorts
        if start_cursor:
            data["start_cursor"] = start_cursor
        if page_size:
            data["page_size"] = min(page_size, 100)
        
        return await self._make_request("POST", f"databases/{database_id}/query", data)
    
    async def get_page(self, page_id: str) -> dict:
        """
        获取页面信息
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面信息
        """
        logger.info(f"获取页面信息: {page_id}")
        return await self._make_request("GET", f"pages/{page_id}")
    
    async def get_page_content(self, page_id: str) -> dict:
        """
        获取页面内容（块）
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面内容块列表
        """
        logger.info(f"获取页面内容: {page_id}")
        return await self._make_request("GET", f"blocks/{page_id}/children")
    
    async def search(
        self, 
        query: Optional[str] = None,
        filter_conditions: Optional[dict] = None,
        sorts: Optional[List[dict]] = None,
        start_cursor: Optional[str] = None,
        page_size: Optional[int] = None
    ) -> dict:
        """
        搜索页面和数据库
        
        Args:
            query: 搜索查询字符串
            filter_conditions: 过滤条件
            sorts: 排序条件
            start_cursor: 分页游标
            page_size: 页面大小
            
        Returns:
            搜索结果
        """
        logger.info(f"搜索内容: {query}")
        
        data = {}
        if query:
            data["query"] = query
        if filter_conditions:
            data["filter"] = filter_conditions
        if sorts:
            data["sorts"] = sorts
        if start_cursor:
            data["start_cursor"] = start_cursor
        if page_size:
            data["page_size"] = min(page_size, 100)
        
        return await self._make_request("POST", "search", data)
    
    async def get_block_children(self, block_id: str, start_cursor: Optional[str] = None) -> dict:
        """
        获取块的子块
        
        Args:
            block_id: 块ID
            start_cursor: 分页游标
            
        Returns:
            子块列表
        """
        logger.info(f"获取块子内容: {block_id}")
        
        params = {}
        if start_cursor:
            params["start_cursor"] = start_cursor
        
        return await self._make_request("GET", f"blocks/{block_id}/children", params=params)


# 创建默认客户端实例的工厂函数
def create_notion_client(config: Optional[NotionConfig] = None) -> NotionClient:
    """
    创建Notion客户端实例
    
    Args:
        config: Notion配置
        
    Returns:
        Notion客户端实例
    """
    return NotionClient(config)

