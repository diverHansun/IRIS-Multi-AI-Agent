from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.llm import LLMService


class LLMModelCommand(BaseCommand):
    name = "model"
    engine_scope = ("llm",)
    help_text = "Switch provider/model for the LLM engine."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.split()
        if len(parts) < 1:
            return CommandResult.error("Usage: /model <provider> [model]")
        provider = parts[0].lower()
        model = parts[1] if len(parts) > 1 else None

        if ctx.current_engine != "llm":
            return CommandResult.error("/model for LLMs is only available in the llm engine.")

        service = LLMService()
        result = await service.switch_model(ctx, provider, model)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["LLMModelCommand"]

