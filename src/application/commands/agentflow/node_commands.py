"""AgentFlow node exploration commands (placeholders)."""

from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult


class NodesCommand(BaseCommand):
    name = "nodes"
    engine_scope = ("agentflow",)
    help_text = "List nodes in the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("AgentFlow node listing is reserved for future implementation.")


class VisualizeCommand(BaseCommand):
    name = "visualize"
    engine_scope = ("agentflow",)
    help_text = "Visualize the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("AgentFlow visualization is reserved for future implementation.")


__all__ = ["NodesCommand", "VisualizeCommand"]
