"""AgentFlow model selection commands (placeholders)."""

from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult


class AgentFlowModelCommand(BaseCommand):
    name = "graph-model"
    aliases = ()
    engine_scope = ("agentflow",)
    help_text = "Select a model for the active graph."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("AgentFlow model selection is not implemented yet.")


__all__ = ["AgentFlowModelCommand"]
