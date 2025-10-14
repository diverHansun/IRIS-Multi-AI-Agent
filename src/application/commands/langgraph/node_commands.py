"""
LangGraph node exploration commands (placeholders).
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class NodesCommand(BaseCommand):
    name = "nodes"
    engine_scope = ("langgraph",)
    help_text = "List nodes in the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("LangGraph node listing is reserved for future implementation.")


class VisualizeCommand(BaseCommand):
    name = "visualize"
    engine_scope = ("langgraph",)
    help_text = "Visualize the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("LangGraph visualization is reserved for future implementation.")


__all__ = ["NodesCommand", "VisualizeCommand"]
