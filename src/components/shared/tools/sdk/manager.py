"""
SDK Tool Manager

Provides unified interface to manage and access all SDK tools
"""
import logging
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

logger = logging.getLogger(__name__)


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
        tools: List[BaseTool] = []
        stats = {"total": 0, "success": 0, "failed": 0}

        loaders: List[Dict[str, Any]] = [
            {"name": "math", "loader": get_available_math_tools},
            {"name": "tavily", "loader": get_available_tavily_tools},
            {"name": "zhipu", "loader": get_available_zhipu_tools},
            {"name": "search", "loader": get_all_search_tools},
            {"name": "time", "loader": get_available_time_tools},
            {"name": "amap", "loader": get_available_amap_tools},
            {"name": "notion", "loader": get_available_notion_tools, "optional": True},
            {"name": "okx", "loader": get_available_okx_tools},
        ]

        logger.info("Loading SDK tools from %d sources", len(loaders))
        for entry in loaders:
            name = entry["name"]
            loader: Callable[[], List[BaseTool]] = entry["loader"]
            optional = entry.get("optional", False)
            stats["total"] += 1

            logger.debug("Loading %s tools...", name)
            try:
                available = loader()
                count = len(available) if available else 0
                tools.extend(available or [])
                stats["success"] += 1
                logger.info("Loaded %d %s tools", count, name)
            except Exception as exc:
                stats["failed"] += 1
                level = logger.warning if optional else logger.error
                level("Failed to load %s tools: %s", name, exc, exc_info=not optional)

        logger.info(
            "SDK tools load complete: %d/%d sources succeeded, total tools: %d",
            stats["success"],
            stats["total"],
            len(tools),
        )
        return tools

    @staticmethod
    def get_tools_by_category() -> Dict[str, List[BaseTool]]:
        """
        Get tools organized by category

        Returns:
            Dict[str, List[BaseTool]]: Dictionary of tools grouped by category
        """
        logger.debug("Building SDK tools by category")
        tavily_tools = []
        zhipu_tools = []
        search_tools = []

        try:
            tavily_tools = get_available_tavily_tools()
        except Exception as exc:
            logger.error("Failed to load tavily tools for category listing: %s", exc, exc_info=True)

        try:
            zhipu_tools = get_available_zhipu_tools()
        except Exception as exc:
            logger.error("Failed to load zhipu tools for category listing: %s", exc, exc_info=True)

        try:
            search_tools = get_all_search_tools()
        except Exception as exc:
            logger.error("Failed to load search tools for category listing: %s", exc, exc_info=True)

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
            "okx": get_available_okx_tools(),
        }

        # Add Notion tools with error handling
        try:
            categories["notion"] = get_available_notion_tools()
        except Exception as exc:
            logger.warning("Failed to load notion tools for category listing: %s", exc)
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
