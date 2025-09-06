"""
Global MCP package

Provides a singleton manager for MCP servers and tools so that all agents
share the same toolset. The manager is resilient to missing optional
dependencies and will gracefully disable MCP if not configured.
"""

from .manager import GlobalMCPManager

__all__ = ["GlobalMCPManager"]

