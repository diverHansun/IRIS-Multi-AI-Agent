"""
LangGraph model selection commands (placeholders).
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class LangGraphModelCommand(BaseCommand):
    name = "graph-model"
    aliases = ()
    engine_scope = ("langgraph",)
    help_text = "Select a model for the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("LangGraph model selection is not implemented yet.")


__all__ = ["LangGraphModelCommand"]
