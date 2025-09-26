"""
SDK工具管理器

提供统一的接口来管理和获取所有SDK工具
"""
from typing import List, Dict, Any, Callable
from langchain_core.tools import BaseTool

from .calculate.math_tools import get_available_math_tools
from .search.search_tools import get_available_search_tools
from .search.tavily_search_tool import get_available_tavily_tools
from .time.provider import get_available_time_tools
from .amap.provider import get_available_amap_tools
from .notion.langchain_tools import get_available_notion_tools
from .okx_market.langchain_tools import get_available_okx_tools


class SDKToolManager:
    """
    SDK工具统一管理器
    提供统一接口获取和管理各种SDK工具
    """
    
    @staticmethod
    def get_all_tools() -> List[BaseTool]:
        """
        获取所有SDK工具
        
        Returns:
            List[BaseTool]: 所有SDK工具列表
        """
        tools = []
        
        # 数学工具
        math_tools = get_available_math_tools()
        if math_tools:
            tools.extend(math_tools)
        
        # 搜索工具
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            tools.extend(tavily_tools)

        search_tools = get_available_search_tools()
        if search_tools:
            tools.extend(search_tools)
        
        # 时间工具
        time_tools = get_available_time_tools()
        if time_tools:
            tools.extend(time_tools)
        
        # 高德地图工具
        amap_tools = get_available_amap_tools()
        if amap_tools:
            tools.extend(amap_tools)
        
        # Notion工具
        try:
            notion_tools = get_available_notion_tools()
            if notion_tools:
                tools.extend(notion_tools)
        except Exception:
            pass  # Notion工具可选，失败时跳过
        
        # OKX加密货币工具
        okx_tools = get_available_okx_tools()
        if okx_tools:
            tools.extend(okx_tools)
        
        return tools
    
    @staticmethod
    def get_tools_by_category() -> Dict[str, List[BaseTool]]:
        """
        按类别获取工具
        
        Returns:
            Dict[str, List[BaseTool]]: 按类别分组的工具字典
        """
        tavily_tools = get_available_tavily_tools()
        search_tools = get_available_search_tools()
        
        # 合并所有搜索工具
        all_search_tools = []
        if tavily_tools:
            all_search_tools.extend(tavily_tools)
        all_search_tools.extend(search_tools)
        
        return {
            "calculate": get_available_math_tools(),
            "search": all_search_tools,
            "time": get_available_time_tools(),
            "amap": get_available_amap_tools(),
            "notion": get_available_notion_tools(),
            "okx": get_available_okx_tools()
        }
    
    @staticmethod
    def get_tool_by_name(tool_name: str) -> BaseTool:
        """
        根据工具名称获取特定工具
        
        Args:
            tool_name (str): 工具名称
            
        Returns:
            BaseTool: 指定工具
        """
        all_tools = SDKToolManager.get_all_tools()
        for tool in all_tools:
            if tool.name == tool_name:
                return tool
        raise ValueError(f"未找到名为 '{tool_name}' 的工具")
    
    @staticmethod
    def get_available_tools_count() -> int:
        """
        获取可用工具总数
        
        Returns:
            int: 可用工具数量
        """
        return len(SDKToolManager.get_all_tools())
    
    @staticmethod
    def get_tools_info() -> Dict[str, Any]:
        """
        获取工具统计信息
        
        Returns:
            Dict[str, Any]: 工具统计信息
        """
        categories = SDKToolManager.get_tools_by_category()
        info = {}
        total_count = 0
        
        for category, tools in categories.items():
            count = len(tools) if tools else 0
            info[category] = {
                "count": count,
                "tools": [tool.name for tool in tools] if tools else []
            }
            total_count += count
        
        info["total"] = total_count
        return info