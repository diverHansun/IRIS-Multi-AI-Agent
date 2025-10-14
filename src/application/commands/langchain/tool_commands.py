"""
LangChain commands managing MCP and connector tools.
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class MCPCommand(BaseCommand):
    name = "mcp"
    engine_scope = ("langchain", "langgraph")
    help_text = "Manage MCP tools."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("MCP tooling will be implemented during migration.")


class ConnectorCommand(BaseCommand):
    name = "connector"
    engine_scope = ("langchain", "langgraph")
    help_text = "Manage connector tools."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("Connector tooling will be implemented during migration.")


__all__ = ["MCPCommand", "ConnectorCommand"]
