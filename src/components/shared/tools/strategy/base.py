"""
Base Tool Provider Interface

Defines the abstract interface for all tool providers using strategy pattern.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class ToolProvider(ABC):
    """
    Abstract base class for tool providers.

    All tool sources (SDK, MCP, Connector) should implement this interface
    to enable uniform tool management through the UnifiedToolManager.
    """

    def __init__(self, name: str):
        """
        Initialize tool provider.

        Args:
            name: Provider name for logging and identification
        """
        self.name = name
        self._tools: List[BaseTool] = []
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the tool provider.

        This method should load and prepare all tools from this source.
        Must be called before get_tools().
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """
        Get list of tools from this provider.

        Returns:
            List of BaseTool instances

        Raises:
            RuntimeError: If provider not initialized
        """
        pass

    @abstractmethod
    async def reload(self) -> None:
        """
        Reload tools from this provider.

        Useful for refreshing tools without restarting the application.
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get provider status information.

        Returns:
            Dictionary containing status information
        """
        return {
            "name": self.name,
            "initialized": self._initialized,
            "tool_count": len(self._tools),
            "tools": [tool.name for tool in self._tools] if self._tools else []
        }

    def is_initialized(self) -> bool:
        """Check if provider is initialized."""
        return self._initialized

    def get_tool_count(self) -> int:
        """Get number of tools provided."""
        return len(self._tools)
