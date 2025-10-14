"""
LangChain model management commands such as /model.
"""

from __future__ import annotations

from ...services.langchain import LangChainService
from ..base import BaseCommand, CommandResult


class ModelCommand(BaseCommand):
    name = "model"
    engine_scope = ("langchain",)
    help_text = "Switch LangChain provider/model."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.split()
        if len(parts) < 1:
            return CommandResult.error("Usage: /model <provider> [model]")
        provider = parts[0].lower()
        model = parts[1] if len(parts) > 1 else None

        service = LangChainService()
        result = await service.switch_model(ctx, provider, model)
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["ModelCommand"]
