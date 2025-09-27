"""
Connector Tool Manager - Aggregates connector tools with source tagging
"""

from typing import Dict, List, Optional
from langchain_core.tools import BaseTool
from .crawl4ai import get_tools


class ConnectorToolManager:
    """
    Manages connector tools, mirroring SDKToolManager API but for connector-based tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all connector tools."""
        tools = get_tools()
        for tool in tools:
            self._tools[tool.name] = tool
    
    def get_all_tools(self) -> List[BaseTool]:
        """Get all connector tools."""
        return list(self._tools.values())
    
    def get_tool_by_name(self, name: str) -> Optional[BaseTool]:
        """Get a specific connector tool by name."""
        return self._tools.get(name)
    
    def get_tools_info(self) -> Dict[str, str]:
        """Get information about all connector tools."""
        return {name: tool.description for name, tool in self._tools.items()}
    
    def get_tool_count(self) -> int:
        """Get the count of connector tools."""
        return len(self._tools)

    def reload_tools(self) -> Dict[str, any]:
        """Reload all connector tools and return status."""
        try:
            old_count = len(self._tools)
            self._tools.clear()
            self._initialize_tools()
            new_count = len(self._tools)

            return {
                "success": True,
                "old_count": old_count,
                "new_count": new_count,
                "message": f"Reloaded {new_count} connector tools"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to reload connector tools: {str(e)}"
            }