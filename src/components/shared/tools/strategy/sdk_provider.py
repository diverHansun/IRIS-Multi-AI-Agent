"""
SDK Tool Provider

Provides tools from the SDK tool manager.
"""

import logging
from typing import List

from langchain_core.tools import BaseTool

from .base import ToolProvider
from ..sdk import SDKToolManager

logger = logging.getLogger(__name__)


class SDKToolProvider(ToolProvider):
    """Tool provider for SDK tools."""

    def __init__(self):
        """Initialize SDK tool provider."""
        super().__init__(name="sdk")

    async def initialize(self) -> None:
        """
        Initialize SDK tools.

        SDK tools are loaded from the SDKToolManager.
        """
        if self._initialized:
            logger.debug(f"{self.name} provider already initialized")
            return

        try:
            logger.info(f"Initializing {self.name} tool provider...")
            self._tools = SDKToolManager.get_all_tools()
            self._initialized = True
            logger.info(f"{self.name} provider initialized: {len(self._tools)} tools loaded")
        except Exception as e:
            logger.error(f"Failed to initialize {self.name} provider: {e}")
            raise

    def get_tools(self) -> List[BaseTool]:
        """
        Get SDK tools.

        Returns:
            List of SDK tools

        Raises:
            RuntimeError: If provider not initialized
        """
        if not self._initialized:
            raise RuntimeError(f"{self.name} provider not initialized. Call initialize() first.")

        return self._tools

    async def reload(self) -> None:
        """
        Reload SDK tools.

        Note: SDK tools are typically static and don't need reloading,
        but this method is provided for interface compatibility.
        """
        logger.info(f"Reloading {self.name} tools...")
        self._initialized = False
        await self.initialize()
        logger.info(f"{self.name} tools reloaded: {len(self._tools)} tools")
