"""
Dify session maintenance commands.
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class DifyResetCommand(BaseCommand):
    name = "reset"
    engine_scope = ("dify",)
    help_text = "Reset the current Dify conversation."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("Dify reset is not implemented yet.")


class DifyReconnectCommand(BaseCommand):
    name = "reconnect"
    engine_scope = ("dify",)
    help_text = "Reconnect to the Dify service."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("Dify reconnect is not implemented yet.")


__all__ = ["DifyResetCommand", "DifyReconnectCommand"]
