"""Deep agent command handler."""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Dict, Iterable

logger = logging.getLogger(__name__)

from src.agents.deepagents.managers import subagent_manager
from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.agent.deep.agent_lifecycle import create_default_deep_agent
from src.application.services.agent.deep.middleware import (
    PatchToolCallsService,
    RealFilesystemMiddlewareService,
    SubagentsMiddlewareService,
    VirtualFilesystemMiddlewareService,
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
            "config": self._handle_config,
            "filesystem": self._handle_filesystem,
        }

        handler = handlers.get(action)
        if handler is None:
            return CommandResult.error(self._usage())

        result = handler(ctx, rest)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _usage(self) -> str:
        return (
            "Usage:\n"
            "  /deep status\n"
            "  /deep config reload\n"
            "  /deep filesystem status\n"
            "  /deep filesystem reload"
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
        filesystem_cfg = middleware_cfg.get("filesystem", {})
        virtual_cfg = filesystem_cfg.get("virtual", filesystem_cfg if "virtual" not in filesystem_cfg else {})
        real_cfg = filesystem_cfg.get("real", {})

        virtual_fs_service = VirtualFilesystemMiddlewareService(virtual_cfg)
        real_fs_service = RealFilesystemMiddlewareService(real_cfg)
        subagents_service = SubagentsMiddlewareService(middleware_cfg.get("subagents", {}))
        patch_service = PatchToolCallsService(middleware_cfg.get("patch_tool_calls", {}))
        skills_cfg = middleware_cfg.get("skills", {})
        if not isinstance(skills_cfg, dict):
            skills_cfg = {}
        prompt_cfg = skills_cfg.get("prompt", {})
        if not isinstance(prompt_cfg, dict):
            prompt_cfg = {}
        max_skills_in_prompt = prompt_cfg.get("max_skills_in_prompt", 20)
        try:
            max_skills_in_prompt = int(max_skills_in_prompt)
        except (TypeError, ValueError):
            max_skills_in_prompt = 20

        middleware_status = {
            "virtual_filesystem": virtual_fs_service.describe(),
            "real_filesystem": real_fs_service.describe(),
            "subagents": subagents_service.describe(),
            "patch_tool_calls": patch_service.describe(),
            "skills": {
                "enabled": bool(skills_cfg.get("enabled", True)),
                "max_skills_in_prompt": max_skills_in_prompt,
            },
        }

        payload = {
            "provider": info.get("provider") or config.get("provider"),
            "model": info.get("model") or config.get("model"),
            "function_type": info.get("function_type") or config.get("function_type"),
            "subagents": subagent_names,
            "middleware": middleware_status,
        }

        function_value = payload.get("function_type") or "research"
        fs_enabled = "enabled" if middleware_status["virtual_filesystem"].get("enabled") else "disabled"
        fs_long_term_memory = (
            "enabled" if middleware_status["virtual_filesystem"].get("long_term_memory") else "disabled"
        )
        real_fs_enabled = "enabled" if middleware_status["real_filesystem"].get("enabled") else "disabled"

        message = (
            "Deep Agent Status:\n"
            f"- Provider: {payload.get('provider')}\n"
            f"- Model: {payload.get('model')}\n"
            f"- Function: {function_value}\n"
            f"- Active Subagents: {', '.join(subagent_names) if subagent_names else 'none'}\n"
            f"- Virtual Filesystem: {fs_enabled} (long-term memory: {fs_long_term_memory})\n"
            f"- Real Filesystem: {real_fs_enabled}\n"
            f"- Skills: {'enabled' if middleware_status['skills']['enabled'] else 'disabled'} "
            f"(max in prompt: {middleware_status['skills']['max_skills_in_prompt']})\n"
            f"- Subagents Middleware: {'enabled' if middleware_status['subagents']['enabled'] else 'disabled'}\n"
            f"- Patch Tool Calls: {'enabled' if middleware_status['patch_tool_calls']['enabled'] else 'disabled'}"
        )
        return CommandResult.success(message, payload=payload)

    def _handle_config(self, ctx, args: list[str]) -> CommandResult:
        """Reload deep agent configuration from files."""
        if not args or args[0].lower() != "reload":
            return CommandResult.error("Usage: /deep config reload")

        deepagents_provider_registry.reload()
        return CommandResult.success("Deep agent configuration reloaded.")

    async def _handle_filesystem(self, ctx, args: list[str]) -> CommandResult:
        if not args:
            return CommandResult.error("Usage: /deep filesystem <status|reload>")

        command = args[0].lower()
        if command == "status":
            return self._filesystem_status(ctx)
        if command == "reload":
            return await self._filesystem_reload(ctx)
        return CommandResult.error("Usage: /deep filesystem <status|reload>")

    # ------------------------------------------------------------------ filesystem helpers
    def _filesystem_status(self, ctx) -> CommandResult:
        config = ctx.get_engine_config("agent")
        middleware_cfg = config.get("middleware", {}) or {}
        filesystem_cfg = middleware_cfg.get("filesystem", {})

        if isinstance(filesystem_cfg, str):
            filesystem_cfg = {}

        virtual_cfg = {}
        real_cfg = {}
        if isinstance(filesystem_cfg, dict):
            if "virtual" in filesystem_cfg or "real" in filesystem_cfg:
                virtual_cfg = filesystem_cfg.get("virtual", {})
                real_cfg = filesystem_cfg.get("real", {})
            else:
                virtual_cfg = filesystem_cfg
        virtual_service = VirtualFilesystemMiddlewareService(
            virtual_cfg if isinstance(virtual_cfg, dict) else {}
        )
        real_service = RealFilesystemMiddlewareService(
            real_cfg if isinstance(real_cfg, dict) else {}
        )

        virtual_info = virtual_service.describe()
        real_info = real_service.describe()

        message_lines = [
            "Filesystem Status:",
            self._format_virtual_section(virtual_info),
            "",
            self._format_real_section(real_info),
        ]

        payload = {
            "virtual_filesystem": virtual_info,
            "real_filesystem": real_info,
        }
        return CommandResult.success("\n".join(message_lines), payload=payload)

    async def _filesystem_reload(self, ctx) -> CommandResult:
        deepagents_provider_registry.reload()
        config = ctx.get_engine_config("agent")
        config["middleware"] = deepagents_provider_registry.get_middleware_config()

        agent_type = config.get("agent_type", "deep")
        reinit_message = "Filesystem configuration reloaded."

        if agent_type == "deep":
            try:
                config["agent_instance"] = None
                agent, info = await create_default_deep_agent(ctx, target="deep")
                config["agent_instance"] = agent
                if info.get("middleware"):
                    config["middleware"] = info["middleware"]
                reinit_message = (
                    "Filesystem configuration reloaded and deep agent reinitialised."
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to reinitialise deep agent after filesystem reload: %s",
                    exc,
                )
                reinit_message = (
                    "Filesystem configuration reloaded, but agent reinitialisation failed. "
                    "It will be created on next use."
                )

        return CommandResult.success(reinit_message)

    def _format_virtual_section(self, info: Dict[str, Any]) -> str:
        enabled = "yes" if info.get("enabled") else "no"
        long_term = "enabled" if info.get("long_term_memory") else "disabled"
        limit = info.get("tool_token_limit_before_evict")
        limit_text = str(limit) if limit is not None else "n/a"
        lines = [
            "Virtual Filesystem:",
            f"  - enabled: {enabled}",
            f"  - long_term_memory: {long_term}",
            f"  - eviction_threshold: {limit_text}",
        ]
        return "\n".join(lines)

    def _format_real_section(self, info: Dict[str, Any]) -> str:
        enabled = "yes" if info.get("enabled") else "no"
        project_root = info.get("project_root") or "${AUTO_DETECT}"
        allowed_paths = self._format_list(info.get("allowed_paths", []))
        excluded_paths = self._format_list(info.get("excluded_paths", []))
        extensions = self._format_list(info.get("allowed_extensions", []), limit=6)
        max_size = info.get("max_file_size")
        glob_limit = info.get("glob_max_results")
        grep_limit = info.get("grep_max_results")
        grep_size = info.get("grep_max_file_size")
        ignore_hidden = "yes" if info.get("ignore_hidden_files") else "no"

        lines = [
            "Real Filesystem:",
            f"  - enabled: {enabled}",
            f"  - project_root: {project_root}",
            f"  - allowed_paths: {allowed_paths}",
            f"  - excluded_paths: {excluded_paths}",
            f"  - allowed_extensions: {extensions}",
            f"  - max_file_size(bytes): {max_size if max_size is not None else 'n/a'}",
            f"  - glob_max_results: {glob_limit if glob_limit is not None else 'n/a'}",
            f"  - grep_max_results: {grep_limit if grep_limit is not None else 'n/a'}",
            f"  - grep_max_file_size(bytes): {grep_size if grep_size is not None else 'n/a'}",
            f"  - ignore_hidden_files: {ignore_hidden}",
        ]
        return "\n".join(lines)

    def _format_list(self, values: Iterable[str], *, limit: int = 3) -> str:
        items = list(values or [])
        if not items:
            return "n/a"
        if len(items) <= limit:
            return ", ".join(items)
        return ", ".join(items[:limit]) + f", ... (+{len(items) - limit})"


__all__ = ["DeepCommand"]
