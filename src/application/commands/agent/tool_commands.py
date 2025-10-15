"""
Agent engine commands managing MCP and connector tools.
"""

from __future__ import annotations

from typing import List

from src.application.cli.gui import render as gui_render
from src.application.services.shared.tools import connector_control, mcp_control
from src.application.commands.base import BaseCommand, CommandResult


class MCPCommand(BaseCommand):
    name = "mcp"
    engine_scope = ("agent", "agentflow")
    help_text = "Manage MCP tools."

    async def execute(self, ctx, args: str) -> CommandResult:
        tokens = args.strip().split()
        if not tokens:
            return CommandResult.error("Usage: /mcp status [-v] | /mcp tools [--json] | /mcp reload")

        action = tokens[0].lower()
        options = tokens[1:]

        if action == "status":
            verbose = any(opt in ("-v", "--verbose") for opt in options)
            result = await mcp_control.mcp_status(verbose=verbose)
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to retrieve MCP status."))
            gui_render.render_mcp_status(ctx.console, result.get("payload", {}), verbose=verbose)
            return CommandResult.success(result.get("message", ""))

        if action == "tools":
            json_flag = any(opt == "--json" for opt in options)
            result = await mcp_control.mcp_tools(json_flag=json_flag)
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to list MCP tools."))
            tools = result.get("payload", {}).get("tools", [])
            gui_render.render_mcp_tools(ctx.console, tools, json_flag=json_flag)
            return CommandResult.success(result.get("message", ""))

        if action == "reload":
            result = await mcp_control.mcp_reload()
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to reload MCP configuration."))
            ctx.console.print_json(data=result.get("payload", {}))
            return CommandResult.success(result.get("message", "MCP configuration reloaded."))

        return CommandResult.error("Usage: /mcp status [-v] | /mcp tools [--json] | /mcp reload")


class ConnectorCommand(BaseCommand):
    name = "connector"
    engine_scope = ("agent", "agentflow")
    help_text = "Manage connector tools."

    async def execute(self, ctx, args: str) -> CommandResult:
        tokens = args.strip().split()
        if not tokens:
            return CommandResult.error("Usage: /connector status [-v] | /connector tools [--json] | /connector reload")

        action = tokens[0].lower()
        options = tokens[1:]

        if action == "status":
            verbose = any(opt in ("-v", "--verbose") for opt in options)
            result = await connector_control.connector_status(verbose=verbose)
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to retrieve connector status."))
            gui_render.render_connector_status(ctx.console, result.get("payload", {}), verbose=verbose)
            return CommandResult.success(result.get("message", ""))

        if action == "tools":
            json_flag = any(opt == "--json" for opt in options)
            result = await connector_control.connector_tools(json_flag=json_flag)
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to list connector tools."))
            tools = result.get("payload", {}).get("tools", {})
            gui_render.render_connector_tools(ctx.console, tools, json_flag=json_flag)
            return CommandResult.success(result.get("message", ""))

        if action == "reload":
            result = await connector_control.connector_reload()
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to reload connector tools."))
            ctx.console.print_json(data=result.get("payload", {}))
            return CommandResult.success(result.get("message", "Connector tools reloaded."))

        return CommandResult.error("Usage: /connector status [-v] | /connector tools [--json] | /connector reload")


__all__ = ["MCPCommand", "ConnectorCommand"]

