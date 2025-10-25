"""Model switching command for deep agent mode."""

from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.agent.deep import DeepAgentService


class ModelCommand(BaseCommand):
    name = "model"
    engine_scope = ("agent",)
    help_text = "Switch provider/model for the deep agent engine."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.split()
        if len(parts) < 1:
            return CommandResult.error("Usage: /model <provider> [model]")
        provider = parts[0].lower()
        model = parts[1] if len(parts) > 1 else None

        if ctx.current_engine != "agent":
            return CommandResult.error("/model for agents is only available in the agent engine.")

        config = ctx.get_engine_config("agent")
        if config.get("agent_type") != "deep":
            return CommandResult.error("Use /model for basic mode. Current mode is basic.")

        service = DeepAgentService()
        result = await service.switch_model(ctx, provider, model)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["ModelCommand"]
