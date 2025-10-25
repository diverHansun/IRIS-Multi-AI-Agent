"""Deep agent command handler."""

from __future__ import annotations

import json
from typing import Any, Dict

from src.agents.deepagents.managers import subagent_manager
from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.agent.deep.middleware import (
    FilesystemMiddlewareService,
    PatchToolCallsService,
    SubagentsMiddlewareService,
)
from src.core.providers import deepagents_provider_registry


class DeepCommand(BaseCommand):
    name = "deep"
    engine_scope = ("agent",)
    help_text = "Manage deep agent status, middleware, and configuration."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.strip().split()
        if not parts:
            return CommandResult.info(self._usage())

        action = parts[0].lower()
        rest = parts[1:]

        handlers = {
            "status": self._handle_status,
            "filesystem": self._handle_filesystem,
            "config": self._handle_config,
        }

        handler = handlers.get(action)
        if handler is None:
            return CommandResult.error(self._usage())

        return handler(ctx, rest)

    def _usage(self) -> str:
        return (
            "Usage:\n"
            "  /deep status\n"
            "  /deep filesystem <read-only|ask-before-edit|auto-edit>\n"
            "  /deep config reload"
        )

    def _handle_status(self, ctx, _: list[str]) -> CommandResult:
        """Display comprehensive deep agent status including middleware."""
        config = ctx.get_engine_config("agent")
        agent = config.get("agent_instance")
        info: Dict[str, Any] = agent.get_info() if agent and hasattr(agent, "get_info") else {}

        # Extract subagent information
        subagent_meta = info.get("subagents") or []
        if isinstance(subagent_meta, list):
            subagent_names = [
                entry.get("name")
                for entry in subagent_meta
                if isinstance(entry, dict) and entry.get("name")
            ]
        else:
            subagent_names = []

        # Get middleware status
        middleware_cfg = config.get("middleware", {})
        filesystem_service = FilesystemMiddlewareService(middleware_cfg.get("filesystem", {}))
        subagents_service = SubagentsMiddlewareService(middleware_cfg.get("subagents", {}))
        patch_service = PatchToolCallsService(middleware_cfg.get("patch_tool_calls", {}))

        middleware_status = {
            "filesystem": filesystem_service.describe(),
            "subagents": subagents_service.describe(),
            "patch_tool_calls": patch_service.describe(),
        }

        payload = {
            "provider": info.get("provider") or config.get("provider"),
            "model": info.get("model") or config.get("model"),
            "function_type": info.get("function_type") or config.get("function_type"),
            "subagents": subagent_names,
            "middleware": middleware_status,
        }

        function_value = payload.get("function_type") or "research"
        fs_mode = middleware_status["filesystem"].get("mode", "unknown")
        fs_enabled = "enabled" if middleware_status["filesystem"].get("enabled") else "disabled"

        message = (
            "Deep Agent Status:\n"
            f"- Provider: {payload.get('provider')}\n"
            f"- Model: {payload.get('model')}\n"
            f"- Function: {function_value}\n"
            f"- Active Subagents: {', '.join(subagent_names) if subagent_names else 'none'}\n"
            f"- Filesystem: {fs_enabled} (mode: {fs_mode})\n"
            f"- Subagents Middleware: {'enabled' if middleware_status['subagents']['enabled'] else 'disabled'}\n"
            f"- Patch Tool Calls: {'enabled' if middleware_status['patch_tool_calls']['enabled'] else 'disabled'}"
        )
        return CommandResult.success(message, payload=payload)

    def _handle_filesystem(self, ctx, args: list[str]) -> CommandResult:
        if not args:
            return CommandResult.error("Usage: /deep filesystem <read-only|ask-before-edit|auto-edit>")

        mode = args[0].replace("_", "-").lower()
        canonical_map = {
            "read-only": "read_only",
            "ask-before-edit": "ask_before_edit",
            "auto-edit": "auto_edit",
        }
        canonical = canonical_map.get(mode)
        if canonical is None:
            return CommandResult.error("Invalid filesystem mode. Valid modes: read-only, ask-before-edit, auto-edit")

        config = ctx.get_engine_config("agent")
        middleware_config = config.setdefault("middleware", {})
        filesystem_config = middleware_config.setdefault("filesystem", {})
        filesystem_config.setdefault("default_mode", filesystem_config.get("default_mode", canonical))
        filesystem_config["mode"] = canonical

        service = FilesystemMiddlewareService(filesystem_config)
        service.set_mode(canonical)
        filesystem_config.update(service.describe())

        return CommandResult.success(
            f"Filesystem permission mode switched to {mode}.",
            payload=service.describe(),
        )


    def _handle_config(self, ctx, args: list[str]) -> CommandResult:
        """Reload deep agent configuration from files."""
        if not args or args[0].lower() != "reload":
            return CommandResult.error("Usage: /deep config reload")

        deepagents_provider_registry.reload()
        return CommandResult.success("Deep agent configuration reloaded.")


__all__ = ["DeepCommand"]
