"""
MCP客户端模块

基于langchain-mcp-adapters实现标准化的MCP集成，提供网络搜索功能。
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# 尝试导入MCP适配器
MCP_AVAILABLE = False
MCP_CLIENT = None

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    MCP_AVAILABLE = True
    logger.info("✅ langchain-mcp-adapters 已安装")
except ImportError as e:
    logger.warning(f"⚠️ langchain-mcp-adapters 未安装: {e}")
    logger.info("💡 可以使用以下命令安装: pip install langchain-mcp-adapters")


class MCPSearchClient:
    """MCP搜索客户端"""
    
    def __init__(self):
        """初始化MCP搜索客户端"""
        self.client = None
        self.tools = []
        self.is_initialized = False
        self._fallback_tools = None
        
    async def initialize_with_brave_search(self, api_key: Optional[str] = None):
        """
        使用Brave Search MCP服务器初始化
        
        Args:
            api_key: Brave Search API密钥 (可选)
        """
        if not MCP_AVAILABLE:
            logger.warning("MCP适配器不可用，使用备用搜索工具")
            await self._initialize_fallback()
            return False
            
        try:
            # 配置Brave Search MCP服务器
            server_config = {
                "brave-search": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-brave-search"]
                }
            }
            
            # 如果有API密钥，添加到环境变量
            if api_key:
                server_config["brave-search"]["env"] = {"BRAVE_API_KEY": api_key}
            
            # 创建MCP客户端
            self.client = MultiServerMCPClient(server_config)
            
            # 获取工具
            self.tools = await self.client.get_tools()
            self.is_initialized = True
            
            logger.info(f"✅ Brave Search MCP客户端初始化成功，获得 {len(self.tools)} 个工具")
            return True
            
        except Exception as e:
            logger.error(f"❌ Brave Search MCP客户端初始化失败: {e}")
            logger.info("🔄 回退到备用搜索工具")
            await self._initialize_fallback()
            return False
    
    async def initialize_with_web_search(self):
        """
        使用Web Search MCP服务器初始化（简单版本）
        """
        if not MCP_AVAILABLE:
            logger.warning("MCP适配器不可用，使用备用搜索工具")
            await self._initialize_fallback()
            return False
            
        try:
            # 配置简单Web搜索MCP服务器
            server_config = {
                "web-search": {
                    "transport": "stdio",
                    "command": "node",
                    "args": ["dist/index.js"],
                    "cwd": "./web-search-mcp"  # 假设已克隆到此目录
                }
            }
            
            # 创建MCP客户端
            self.client = MultiServerMCPClient(server_config)
            
            # 获取工具
            self.tools = await self.client.get_tools()
            self.is_initialized = True
            
            logger.info(f"✅ Web Search MCP客户端初始化成功，获得 {len(self.tools)} 个工具")
            return True
            
        except Exception as e:
            logger.error(f"❌ Web Search MCP客户端初始化失败: {e}")
            logger.info("🔄 回退到备用搜索工具")
            await self._initialize_fallback()
            return False
    
    async def _initialize_fallback(self):
        """初始化备用搜索工具"""
        try:
            from .search_tools import SEARCH_TOOLS
            self._fallback_tools = SEARCH_TOOLS
            self.is_initialized = True
            logger.info(f"✅ 备用搜索工具初始化成功，共 {len(self._fallback_tools)} 个工具")
        except Exception as e:
            logger.error(f"❌ 备用搜索工具初始化失败: {e}")
            self.is_initialized = False
    
    def get_tools(self) -> List[BaseTool]:
        """
        获取可用的搜索工具
        
        Returns:
            LangChain工具列表
        """
        if not self.is_initialized:
            logger.warning("客户端未初始化")
            return []
        
        # 如果有MCP工具，返回MCP工具
        if self.tools:
            return self.tools
        
        # 否则返回备用工具
        if self._fallback_tools:
            return self._fallback_tools
        
        return []
    
    def is_mcp_enabled(self) -> bool:
        """检查是否启用了真正的MCP功能"""
        return self.client is not None and self.tools
    
    async def search(self, query: str, num_results: int = 5) -> str:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            num_results: 结果数量
            
        Returns:
            搜索结果字符串
        """
        if not self.is_initialized:
            return "搜索客户端未初始化"
        
        try:
            # 如果有MCP工具，使用MCP工具
            if self.tools:
                for tool in self.tools:
                    if 'search' in tool.name.lower():
                        result = await tool.arun(query=query, num_results=num_results)
                        return result
            
            # 使用备用工具
            if self._fallback_tools:
                for tool in self._fallback_tools:
                    if 'search' in tool.name.lower() and not 'detailed' in tool.name.lower():
                        result = tool.run(query)
                        return result
            
            return "没有可用的搜索工具"
            
        except Exception as e:
            logger.error(f"搜索执行失败: {e}")
            return f"搜索时发生错误: {str(e)}"
    
    async def close(self):
        """关闭MCP客户端"""
        if self.client:
            await self.client.close()
            logger.info("MCP客户端已关闭")


# 全局MCP客户端实例
mcp_client = MCPSearchClient()


async def initialize_mcp_search(brave_api_key: Optional[str] = None) -> bool:
    """
    初始化MCP搜索功能
    
    Args:
        brave_api_key: Brave Search API密钥 (可选)
        
    Returns:
        是否初始化成功
    """
    # 首先尝试Brave Search（如果有API密钥）
    if brave_api_key:
        success = await mcp_client.initialize_with_brave_search(brave_api_key)
        if success:
            return True
    
    # 尝试简单Web搜索MCP服务器
    success = await mcp_client.initialize_with_web_search()
    if success:
        return True
    
    # 最后回退到备用工具
    await mcp_client._initialize_fallback()
    return mcp_client.is_initialized


def get_mcp_search_tools() -> List[BaseTool]:
    """
    获取MCP搜索工具
    
    Returns:
        搜索工具列表
    """
    return mcp_client.get_tools()


def is_mcp_available() -> bool:
    """检查MCP是否可用"""
    return MCP_AVAILABLE and mcp_client.is_initialized


def is_mcp_enabled() -> bool:
    """检查是否启用了真正的MCP功能"""
    return mcp_client.is_mcp_enabled()


async def test_mcp_client():
    """测试MCP客户端功能"""
    print("Testing MCP client...")
    
    # 初始化
    print("1. Initializing MCP client...")
    success = await initialize_mcp_search()
    
    if success:
        print(f"SUCCESS: MCP client initialized")
        print(f"   - MCP protocol enabled: {'Yes' if is_mcp_enabled() else 'No (using fallback tools)'}")
        print(f"   - Available tools: {len(get_mcp_search_tools())}")
        
        # 列出工具
        tools = get_mcp_search_tools()
        print("\n2. Available tools:")
        for i, tool in enumerate(tools, 1):
            print(f"   {i}. {tool.name}: {tool.description[:50]}...")
        
        # 测试搜索
        print("\n3. Testing search function:")
        try:
            result = await mcp_client.search("Python tutorial", 3)
            print(f"SUCCESS: Search test completed")
            print(f"   Result preview: {result[:200]}...")
        except Exception as e:
            print(f"FAILED: Search test failed: {e}")
    
    else:
        print("FAILED: MCP client initialization failed")
    
    print("\nMCP client testing completed")


if __name__ == "__main__":
    asyncio.run(test_mcp_client())