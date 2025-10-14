"""
System-level commands such as /help or /exit.
"""

from __future__ import annotations

from ...services import get_current_service
from ..base import BaseCommand, CommandResult


class HelpCommand(BaseCommand):
    name = "help"
    help_text = "Display help information."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult(
            type="render",
            payload={"kind": "help", "engine": ctx.current_engine, "args": args},
        )


class InfoCommand(BaseCommand):
    name = "info"
    help_text = "Show current engine information."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = get_current_service(ctx)
        info = service.get_info(ctx)
        return CommandResult(
            type="render",
            payload={"kind": "info", "data": info, "engine": ctx.current_engine},
        )


class ExitCommand(BaseCommand):
    name = "exit"
    aliases = ("quit",)
    help_text = "Exit the application."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.exit("Goodbye!")


__all__ = ["HelpCommand", "InfoCommand", "ExitCommand"]
