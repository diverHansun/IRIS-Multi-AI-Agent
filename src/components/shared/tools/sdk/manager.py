"""
SDK Tool Manager

Provides unified interface to manage and access all SDK tools
"""
from typing import List, Dict, Any, Callable
from langchain_core.tools import BaseTool

from .calculate.math_tools import get_available_math_tools
from .search import get_all_search_tools
from .tavily_search import get_available_tavily_tools
from .zhipu_search import get_available_zhipu_tools
from .time.adapter import get_available_time_tools
from .amap.adapter import get_available_amap_tools
from .notion.adapter import get_available_notion_tools
from .okx_market.adapter import get_available_okx_tools


class SDKToolManager:
    """
    SDK Tool Manager
    Provides unified interface to access and manage various SDK tools
    """

    @staticmethod
    def get_all_tools() -> List[BaseTool]:
        """
        Get all available SDK tools

        Returns:
            List[BaseTool]: List of all SDK tools
        """
        tools = []

        # Math tools
        math_tools = get_available_math_tools()
        if math_tools:
            tools.extend(math_tools)

        # Search tools - Tavily
        tavily_tools = get_available_tavily_tools()
        if tavily_tools:
            tools.extend(tavily_tools)

        # Search tools - Zhipu
        zhipu_tools = get_available_zhipu_tools()
        if zhipu_tools:
            tools.extend(zhipu_tools)

        # Search tools - All (DuckDuckGo Instant Answer + Legacy HTML scraping)
        search_tools = get_all_search_tools()
        if search_tools:
            tools.extend(search_tools)

        # Time tools
        time_tools = get_available_time_tools()
        if time_tools:
            tools.extend(time_tools)

        # Amap tools
        amap_tools = get_available_amap_tools()
        if amap_tools:
            tools.extend(amap_tools)

        # Notion tools
        try:
            notion_tools = get_available_notion_tools()
            if notion_tools:
                tools.extend(notion_tools)
        except Exception:
            pass  # Notion tools are optional, skip on failure

        # OKX cryptocurrency tools
        okx_tools = get_available_okx_tools()
        if okx_tools:
            tools.extend(okx_tools)

        return tools

    @staticmethod
    def get_tools_by_category() -> Dict[str, List[BaseTool]]:
        """
        Get tools organized by category

        Returns:
            Dict[str, List[BaseTool]]: Dictionary of tools grouped by category
        """
        tavily_tools = get_available_tavily_tools()
        zhipu_tools = get_available_zhipu_tools()
        search_tools = get_all_search_tools()

        # Combine all search tools (Tavily + Zhipu + DuckDuckGo + Legacy)
        all_search_tools = []
        if tavily_tools:
            all_search_tools.extend(tavily_tools)
        if zhipu_tools:
            all_search_tools.extend(zhipu_tools)
        if search_tools:
            all_search_tools.extend(search_tools)

        categories = {
            "calculate": get_available_math_tools(),
            "search": all_search_tools,
            "tavily": tavily_tools if tavily_tools else [],
            "zhipu": zhipu_tools if zhipu_tools else [],
            "time": get_available_time_tools(),
            "amap": get_available_amap_tools(),
            "okx": get_available_okx_tools()
        }

        # Add Notion tools with error handling
        try:
            categories["notion"] = get_available_notion_tools()
        except Exception:
            categories["notion"] = []

        return categories

    @staticmethod
    def get_tool_by_name(tool_name: str) -> BaseTool:
        """
        Get specific tool by name

        Args:
            tool_name: Tool name

        Returns:
            BaseTool: The requested tool

        Raises:
            ValueError: If tool with given name is not found
        """
        all_tools = SDKToolManager.get_all_tools()
        for tool in all_tools:
            if tool.name == tool_name:
                return tool
        raise ValueError(f"Tool '{tool_name}' not found")

    @staticmethod
    def get_available_tools_count() -> int:
        """
        Get total count of available tools

        Returns:
            int: Number of available tools
        """
        return len(SDKToolManager.get_all_tools())

    @staticmethod
    def get_tools_info() -> Dict[str, Any]:
        """
        Get tool statistics information

        Returns:
            Dict[str, Any]: Tool statistics including counts and names by category
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