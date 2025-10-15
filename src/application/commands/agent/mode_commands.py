from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult


class ModeCommand(BaseCommand):
    name = "mode"
    engine_scope = ("agent",)
    help_text = "Switch between basic and deep agent modes."

    async def execute(self, ctx, args: str) -> CommandResult:
        target = args.strip().lower()
        config = ctx.get_engine_config("agent")
        current = config.get("agent_type", "basic")

        if not target:
            return CommandResult.info(f"Current agent mode: {current}")

        if target not in {"basic", "deep"}:
            return CommandResult.error("Usage: /mode <basic|deep>")

        if target == current:
            return CommandResult.info(f"Agent mode already set to {target}.")

        config["agent_type"] = target
        config["agent_instance"] = None

        if target == "deep":
            return CommandResult.error("Deep agent mode is not available yet.")

        return CommandResult.success("Switched to basic agent mode.")


__all__ = ["ModeCommand"]
