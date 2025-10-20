"""
Tools command for listing all available tool providers.
"""

from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.shared.tools import tools_control


class ToolsCommand(BaseCommand):
    name = "tools"
    engine_scope = ("agent", "agentflow")
    help_text = "List available tools from all providers."

    async def execute(self, ctx, args: str) -> CommandResult:
        tokens = args.strip().split()

        if not tokens:
            result = await tools_control.tools_summary()
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to load tools."), payload=result.get("payload"))
            return CommandResult(type="render", payload=result.get("payload"))

        if len(tokens) == 1 and tokens[0].lower() == "--list":
            result = await tools_control.tools_list()
            if result["type"] == "error":
                return CommandResult.error(result.get("message", "Failed to load tools."), payload=result.get("payload"))
            return CommandResult(type="render", payload=result.get("payload"))

        return CommandResult.error("Usage: /tools [--list]")


__all__ = ["ToolsCommand"]
