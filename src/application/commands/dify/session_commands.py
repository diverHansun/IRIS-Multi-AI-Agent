"""
Dify session maintenance commands.
"""

from __future__ import annotations

from ...services.dify import DifyService
from ..base import BaseCommand, CommandResult


class DifyResetCommand(BaseCommand):
    name = "reset"
    engine_scope = ("dify",)
    help_text = "Reset the current Dify conversation."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = DifyService()
        result = await service.reset(ctx)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


class DifyReconnectCommand(BaseCommand):
    name = "reconnect"
    engine_scope = ("dify",)
    help_text = "Reconnect to the Dify service."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = DifyService()
        result = await service.reconnect(ctx)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["DifyResetCommand", "DifyReconnectCommand"]

