"""
Unified Tool Manager

Combines multiple tool providers using the composite pattern.
Provides a single interface for managing tools from all sources.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_core.tools import BaseTool

from .strategy.base import ToolProvider
from .strategy import SDKToolProvider, MCPToolProvider, ConnectorToolProvider

logger = logging.getLogger(__name__)


class UnifiedToolManager:
    """
    Unified tool manager using composite pattern.

    Manages multiple tool providers and provides a single interface
    for tool loading, retrieval, and lifecycle management.
    """

    def __init__(self, auto_register_defaults: bool = True):
        """
        Initialize unified tool manager.

        Args:
            auto_register_defaults: Automatically register default providers
                                   (SDK, MCP, Connector)
        """
        self._providers: Dict[str, ToolProvider] = {}
        self._initialized = False

        if auto_register_defaults:
            self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Register default tool providers."""
        self.register_provider(SDKToolProvider())
        self.register_provider(MCPToolProvider())
        self.register_provider(ConnectorToolProvider())
        logger.debug("Default tool providers registered")

    def register_provider(self, provider: ToolProvider) -> None:
        """
        Register a tool provider.

        Args:
            provider: ToolProvider instance to register

        Raises:
            ValueError: If provider with same name already registered
        """
        if provider.name in self._providers:
            logger.warning(f"Provider '{provider.name}' already registered, replacing")

        self._providers[provider.name] = provider
        logger.debug(f"Provider '{provider.name}' registered")

    def unregister_provider(self, name: str) -> bool:
        """
        Unregister a tool provider.

        Args:
            name: Provider name to unregister

        Returns:
            True if provider was unregistered, False if not found
        """
        if name in self._providers:
            del self._providers[name]
            logger.debug(f"Provider '{name}' unregistered")
            return True
        return False

    async def initialize_all(self) -> None:
        """
        Initialize all registered providers.

        This should be called before get_all_tools().
        """
        if self._initialized:
            logger.debug("Tool manager already initialized")
            return

        logger.info(f"Initializing {len(self._providers)} tool providers...")

        for name, provider in self._providers.items():
            try:
                await provider.initialize()
                logger.debug(f"Provider '{name}' initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize provider '{name}': {e}")
                # Continue with other providers even if one fails

        self._initialized = True
        logger.info("All tool providers initialized")

    def get_all_tools(self) -> List[BaseTool]:
        """
        Get tools from all registered providers.

        Returns:
            Combined list of all tools

        Raises:
            RuntimeError: If manager not initialized
        """
        if not self._initialized:
            raise RuntimeError("Tool manager not initialized. Call initialize_all() first.")

        all_tools = []

        for name, provider in self._providers.items():
            try:
                tools = provider.get_tools()
                all_tools.extend(tools)
                logger.debug(f"Collected {len(tools)} tools from '{name}' provider")
            except Exception as e:
                logger.error(f"Failed to get tools from provider '{name}': {e}")
                # Continue with other providers

        logger.info(f"Total tools collected: {len(all_tools)}")
        return all_tools

    def get_tools_by_provider(self, provider_name: str) -> Optional[List[BaseTool]]:
        """
        Get tools from a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            List of tools from the provider, or None if provider not found
        """
        if provider_name not in self._providers:
            logger.warning(f"Provider '{provider_name}' not found")
            return None

        try:
            return self._providers[provider_name].get_tools()
        except Exception as e:
            logger.error(f"Failed to get tools from provider '{provider_name}': {e}")
            return None

    async def reload_all(self) -> None:
        """
        Reload tools from all providers.

        Useful for refreshing tools without restarting the application.
        """
        logger.info("Reloading all tool providers...")

        for name, provider in self._providers.items():
            try:
                await provider.reload()
                logger.debug(f"Provider '{name}' reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload provider '{name}': {e}")

        logger.info("All tool providers reloaded")

    async def reload_provider(self, provider_name: str) -> bool:
        """
        Reload a specific provider.

        Args:
            provider_name: Name of the provider to reload

        Returns:
            True if successful, False if provider not found or reload failed
        """
        if provider_name not in self._providers:
            logger.warning(f"Provider '{provider_name}' not found")
            return False

        try:
            await self._providers[provider_name].reload()
            logger.info(f"Provider '{provider_name}' reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload provider '{provider_name}': {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all providers.

        Returns:
            Dictionary containing status information for each provider
        """
        status = {
            "initialized": self._initialized,
            "provider_count": len(self._providers),
            "providers": {}
        }

        for name, provider in self._providers.items():
            status["providers"][name] = provider.get_status()

        return status

    def get_tool_count(self) -> int:
        """
        Get total number of tools from all providers.

        Returns:
            Total tool count
        """
        if not self._initialized:
            return 0

        return sum(
            provider.get_tool_count()
            for provider in self._providers.values()
        )

    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._initialized

    def list_providers(self) -> List[str]:
        """
        List all registered provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())
