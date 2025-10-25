"""Unified model switching command for both basic and deep agent modes."""

from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.agent.basic import BasicAgentService
from src.application.services.agent.deep import DeepAgentService


class ModelCommand(BaseCommand):
    """Unified model command that works for both basic and deep agent modes."""

    name = "model"
    engine_scope = ("agent",)
    help_text = "Switch provider/model for the agent engine (works in both basic and deep modes)."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.split()
        if len(parts) < 1:
            return CommandResult.error("Usage: /model <provider> [model]")
        provider = parts[0].lower()
        model = parts[1] if len(parts) > 1 else None

        if ctx.current_engine != "agent":
            return CommandResult.error("/model for agents is only available in the agent engine.")

        # Get current agent type (basic or deep)
        config = ctx.get_engine_config("agent")
        agent_type = config.get("agent_type", "basic")

        # Route to appropriate service based on agent type
        if agent_type == "deep":
            service = DeepAgentService()
        else:
            service = BasicAgentService()

        result = await service.switch_model(ctx, provider, model)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["ModelCommand"]
