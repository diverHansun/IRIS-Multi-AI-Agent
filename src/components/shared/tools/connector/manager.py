"""
Connector Tool Manager - Aggregates connector tools with source tagging
"""

import logging
from typing import Dict, List, Optional
from langchain_core.tools import BaseTool
from .crawl4ai import get_tools

logger = logging.getLogger(__name__)


class ConnectorToolManager:
    """
    Manages connector tools, mirroring SDKToolManager API but for connector-based tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all connector tools."""
        logger.debug("Initializing connector tools")
        try:
            tools = get_tools()
            for tool in tools:
                logger.debug("Registering connector tool: %s", getattr(tool, "name", "<unknown>"))
                self._tools[tool.name] = tool
            logger.info("Connector tools initialized: %d tools loaded", len(self._tools))
        except Exception as exc:
            logger.error("Failed to initialize connector tools: %s", exc, exc_info=True)
            raise
    
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
        logger.info("Reloading connector tools...")
        try:
            old_count = len(self._tools)
            self._tools.clear()
            self._initialize_tools()
            new_count = len(self._tools)

            logger.info("Connector tools reloaded: %d -> %d", old_count, new_count)
            return {
                "success": True,
                "old_count": old_count,
                "new_count": new_count,
                "message": f"Reloaded {new_count} connector tools"
            }
        except Exception as exc:
            logger.error("Failed to reload connector tools: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "message": f"Failed to reload connector tools: {str(exc)}"
            }
