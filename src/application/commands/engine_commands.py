"""
Engine-scoped commands such as /switch.
"""

from __future__ import annotations

from src.application.services import get_current_service
from src.application.commands.base import BaseCommand, CommandResult


class SwitchEngineCommand(BaseCommand):
    name = "switch"
    help_text = "Switch the active engine."
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        engine = args.strip().lower()
        if not engine:
            return CommandResult.error("Usage: /switch <engine>")
        if engine not in ctx.engine_configs:
            return CommandResult.error(f"Unknown engine '{engine}'")

        previous_engine = ctx.current_engine

        if engine == previous_engine:
            return CommandResult.info(f"Already using engine '{engine}'.")

        if previous_engine == "dify":
            from src.application.services.dify import DifyService

            await DifyService().cleanup(ctx)

        ctx.current_engine = engine
        service = get_current_service(ctx)
        init_result = await service.initialize(ctx)
        return CommandResult(
            type=init_result["type"],
            message=init_result.get("message", ""),
            payload=init_result.get("payload"),
        )


__all__ = ["SwitchEngineCommand"]
