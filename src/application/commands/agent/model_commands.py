from __future__ import annotations

from src.application.services.agent.basic import BasicAgentService
from src.application.commands.base import BaseCommand, CommandResult


class ModelCommand(BaseCommand):
    name = "model"
    engine_scope = ("agent", "llm")
    help_text = "Switch provider/model for the current engine."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.split()
        if len(parts) < 1:
            return CommandResult.error("Usage: /model <provider> [model]")
        provider = parts[0].lower()
        model = parts[1] if len(parts) > 1 else None

        if ctx.current_engine == "agent":
            service = BasicAgentService()
        elif ctx.current_engine == "llm":
            from src.application.services.llm import LLMService

            service = LLMService()
        else:
            return CommandResult.error("/model is only available in the agent or llm engines.")

        result = await service.switch_model(ctx, provider, model)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["ModelCommand"]
