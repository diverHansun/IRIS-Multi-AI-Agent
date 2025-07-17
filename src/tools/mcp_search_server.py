"""
MCP搜索服务器

实现基于MCP协议的搜索服务器，提供网络搜索功能。
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

try:
    from mcp import server
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_SERVER_AVAILABLE = True
except ImportError:
    # 如果没有MCP服务器库，我们创建一个简单的FastMCP实现
    MCP_SERVER_AVAILABLE = False

# 导入我们现有的搜索功能
from .search_tools import WebSearchProvider

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    url: str
    description: str
    domain: str
    rank: int
    source: str


class MCPSearchServer:
    """MCP搜索服务器实现"""
    
    def __init__(self):
        """初始化MCP搜索服务器"""
        self.search_provider = WebSearchProvider()
        self.server = None
        
    async def initialize(self):
        """初始化服务器"""
        if not MCP_SERVER_AVAILABLE:
            logger.warning("MCP服务器库未安装，使用简化实现")
            return
            
        # 创建MCP服务器
        self.server = Server("search-server")
        
        # 注册搜索工具
        await self._register_tools()
        
    async def _register_tools(self):
        """注册搜索工具"""
        if not self.server:
            return
            
        @self.server.tool("web_search")
        async def web_search(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
            """
            网络搜索工具
            
            Args:
                query: 搜索查询
                num_results: 返回结果数量
                
            Returns:
                搜索结果列表
            """
            try:
                # 使用现有的搜索提供者
                results = self.search_provider.search_duckduckgo(query, num_results)
                
                if not results:
                    results = self.search_provider.search_bing(query, num_results)
                
                return [
                    {
                        "title": result["title"],
                        "url": result["url"],
                        "description": result["description"],
                        "domain": result["domain"],
                        "rank": result["rank"],
                        "source": result["source"]
                    }
                    for result in results
                ]
                
            except Exception as e:
                logger.error(f"搜索失败: {e}")
                return []
        
        @self.server.tool("get_webpage_content")
        async def get_webpage_content(url: str, max_length: int = 3000) -> str:
            """
            获取网页内容
            
            Args:
                url: 网页URL
                max_length: 最大内容长度
                
            Returns:
                网页文本内容
            """
            try:
                content = self.search_provider.get_page_content(url, max_length)
                return content
            except Exception as e:
                logger.error(f"获取网页内容失败: {e}")
                return f"获取网页内容时发生错误: {str(e)}"
    
    async def run(self):
        """运行MCP服务器"""
        if not MCP_SERVER_AVAILABLE:
            logger.error("MCP服务器库未安装，无法运行服务器")
            return
            
        if not self.server:
            await self.initialize()
            
        # 运行stdio服务器
        await stdio_server(self.server)


class SimpleMCPSearchServer:
    """简化的MCP搜索服务器（当没有MCP库时使用）"""
    
    def __init__(self):
        """初始化简化搜索服务器"""
        self.search_provider = WebSearchProvider()
        self.tools = {
            "web_search": self.web_search,
            "get_webpage_content": self.get_webpage_content
        }
    
    async def web_search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """网络搜索工具"""
        try:
            results = self.search_provider.search_duckduckgo(query, num_results)
            
            if not results:
                results = self.search_provider.search_bing(query, num_results)
            
            return [
                {
                    "title": result["title"],
                    "url": result["url"],
                    "description": result["description"],
                    "domain": result["domain"],
                    "rank": result["rank"],
                    "source": result["source"]
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    async def get_webpage_content(self, url: str, max_length: int = 3000) -> str:
        """获取网页内容"""
        try:
            content = self.search_provider.get_page_content(url, max_length)
            return content
        except Exception as e:
            logger.error(f"获取网页内容失败: {e}")
            return f"获取网页内容时发生错误: {str(e)}"
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """调用工具"""
        if tool_name in self.tools:
            return await self.tools[tool_name](**kwargs)
        else:
            raise ValueError(f"未知工具: {tool_name}")


async def main():
    """主函数 - 启动MCP搜索服务器"""
    if MCP_SERVER_AVAILABLE:
        server = MCPSearchServer()
        await server.run()
    else:
        logger.info("启动简化MCP搜索服务器")
        server = SimpleMCPSearchServer()
        # 简化版本不需要运行stdio服务器
        logger.info("简化MCP搜索服务器已准备就绪")


if __name__ == "__main__":
    asyncio.run(main())