from __future__ import annotations

from ..base import BaseCommand, CommandResult


class StreamCommand(BaseCommand):
    name = "stream"
    engine_scope = ("llm",)
    help_text = "Enable or disable streaming output."

    async def execute(self, ctx, args: str) -> CommandResult:
        action = args.strip()
        config = ctx.get_engine_config("llm")

        if not action:
            status = "enabled" if config.get("streaming", True) else "disabled"
            return CommandResult.info(f"Streaming is currently {status}.")

        normalized = action.lower()
        if normalized in {"on", "enable"}:
            config["streaming"] = True
            return CommandResult.success("Streaming output enabled.")
        if normalized in {"off", "disable"}:
            config["streaming"] = False
            return CommandResult.success("Streaming output disabled.")

        return CommandResult.error("Usage: /stream <on|off>")


__all__ = ["StreamCommand"]
