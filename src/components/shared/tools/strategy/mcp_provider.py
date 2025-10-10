"""
MCP Tool Provider

Provides tools from the Model Context Protocol (MCP) manager.
"""

import logging
from typing import List

from langchain_core.tools import BaseTool

from .base import ToolProvider

logger = logging.getLogger(__name__)


class MCPToolProvider(ToolProvider):
    """Tool provider for MCP tools."""

    def __init__(self):
        """Initialize MCP tool provider."""
        super().__init__(name="mcp")
        self._mcp_manager = None

    async def initialize(self) -> None:
        """
        Initialize MCP tools.

        MCP tools are loaded from the GlobalMCPManager.
        """
        if self._initialized:
            logger.debug(f"{self.name} provider already initialized")
            return

        try:
            logger.info(f"Initializing {self.name} tool provider...")

            # Import here to avoid circular dependency
            from ..mcp import GlobalMCPManager

            # Initialize MCP manager
            await GlobalMCPManager.initialize()
            self._mcp_manager = GlobalMCPManager

            # Get tools
            self._tools = GlobalMCPManager.get_tools()
            self._initialized = True

            logger.info(f"{self.name} provider initialized: {len(self._tools)} tools loaded")

        except ImportError as e:
            logger.warning(f"MCP module not available: {e}")
            self._tools = []
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} provider: {e}")
            self._tools = []
            self._initialized = True

    def get_tools(self) -> List[BaseTool]:
        """
        Get MCP tools.

        Returns:
            List of MCP tools (may be empty if MCP not available)

        Raises:
            RuntimeError: If provider not initialized
        """
        if not self._initialized:
            raise RuntimeError(f"{self.name} provider not initialized. Call initialize() first.")

        return self._tools

    async def reload(self) -> None:
        """
        Reload MCP tools.

        This will reinitialize the MCP manager and refresh all tools.
        """
        logger.info(f"Reloading {self.name} tools...")

        if self._mcp_manager:
            try:
                await self._mcp_manager.reload_config()
                self._tools = self._mcp_manager.get_tools()
                logger.info(f"{self.name} tools reloaded: {len(self._tools)} tools")
            except Exception as e:
                logger.error(f"Failed to reload {self.name} tools: {e}")
        else:
            logger.warning(f"{self.name} manager not available, skipping reload")
