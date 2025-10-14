"""
LangChain commands for LLM catalog and configuration reload.
"""

from __future__ import annotations

from ...services.langchain import LangChainService
from ..base import BaseCommand, CommandResult


class LLMsCommand(BaseCommand):
    name = "llms"
    engine_scope = ("langchain",)
    help_text = "List available models from the catalog."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = LangChainService()
        result = await service.list_catalog()
        if result["type"] == "error":
            return CommandResult(
                type="error",
                message=result.get("message", "Failed to load catalog."),
                payload=result.get("payload"),
            )
        catalog = result.get("payload", {}).get("catalog", {})
        return CommandResult(
            type="render",
            payload={"kind": "llm_catalog", "catalog": catalog},
        )


class ReloadCommand(BaseCommand):
    name = "reload"
    engine_scope = ("langchain",)
    help_text = "Reload provider configuration."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = LangChainService()
        result = service.reload_config()
        return CommandResult(
            type=result["type"],
            message=result.get("message", ""),
            payload=result.get("payload"),
        )


__all__ = ["LLMsCommand", "ReloadCommand"]


