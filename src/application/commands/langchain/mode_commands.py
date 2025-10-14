"""
LangChain mode and streaming commands.
"""

from __future__ import annotations

from ...services.langchain import LangChainService
from ..base import BaseCommand, CommandResult


class ModeCommand(BaseCommand):
    name = "mode"
    engine_scope = ("langchain",)
    help_text = "Toggle between LLM and Agent modes."

    async def execute(self, ctx, args: str) -> CommandResult:
        mode = args.strip()
        if not mode:
            current = ctx.get_engine_config("langchain").get("mode", "llm")
            return CommandResult.info(f"Current mode: {current}")
        service = LangChainService()
        result = service.set_mode(ctx, mode)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


class StreamCommand(BaseCommand):
    name = "stream"
    engine_scope = ("langchain",)
    help_text = "Enable or disable streaming output."

    async def execute(self, ctx, args: str) -> CommandResult:
        action = args.strip()
        if not action:
            streaming = ctx.get_engine_config("langchain").get("streaming", True)
            status = "enabled" if streaming else "disabled"
            return CommandResult.info(f"Streaming is currently {status}.")
        service = LangChainService()
        result = service.set_stream(ctx, action)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["ModeCommand", "StreamCommand"]

