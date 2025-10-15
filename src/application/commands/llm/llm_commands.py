from __future__ import annotations

from src.application.services.llm import LLMService
from src.application.commands.base import BaseCommand, CommandResult


class LLMsCommand(BaseCommand):
    name = "llms"
    engine_scope = ("llm",)
    help_text = "List available LLM models."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = LLMService()
        result = await service.list_catalog()
        if result["type"] == "error":
            return CommandResult(
                type="error",
                message=result.get("message", "Failed to load catalog."),
                payload=result.get("payload"),
            )
        payload = result.get("payload", {})
        return CommandResult(type="render", payload=payload)


class ReloadCommand(BaseCommand):
    name = "reload"
    engine_scope = ("llm",)
    help_text = "Reload provider configuration."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = LLMService()
        result = service.reload_config()
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["LLMsCommand", "ReloadCommand"]
