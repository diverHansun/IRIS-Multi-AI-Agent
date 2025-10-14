"""
LangGraph graph selection commands (placeholders).
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class GraphCommand(BaseCommand):
    name = "graph"
    engine_scope = ("langgraph",)
    help_text = "Select an active graph workflow."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("LangGraph graph selection is not implemented yet.")


__all__ = ["GraphCommand"]
