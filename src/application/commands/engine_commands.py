"""
Engine-scoped commands such as /switch.
"""

from __future__ import annotations

from src.application.services import get_current_service
from src.application.commands.base import BaseCommand, CommandResult


class SwitchEngineCommand(BaseCommand):
    name = "switch"
    help_text = "Switch the active engine."
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        engine = args.strip().lower()
        if not engine:
            return CommandResult.error("Usage: /switch <engine>")
        if engine not in ctx.engine_configs:
            return CommandResult.error(f"Unknown engine '{engine}'")

        previous_engine = ctx.current_engine

        if engine == previous_engine:
            return CommandResult.info(f"Already using engine '{engine}'.")

        if previous_engine == "dify":
            from src.application.services.dify import DifyService

            await DifyService().cleanup(ctx)

        ctx.current_engine = engine

        # Update memory system mode when switching engines
        # LLM and basic agent modes share isolated directories; deep is isolated separately
        if engine in ("llm", "agent"):
            from src.components.shared.memory import (
                SessionManager,
                LLMMemory,
                BasicAgentCheckpointer,
                DeepAgentCheckpointer,
            )
            import logging

            logger = logging.getLogger(__name__)
            agent_config = ctx.get_engine_config("agent")
            agent_type = agent_config.get("agent_type", "basic")
            project_context = getattr(ctx, "project_context", None)
            metadata_manager = getattr(ctx, "metadata_manager", None)

            # Ensure session manager exists
            if not getattr(ctx, "session_manager", None) or getattr(ctx.session_manager, "memory_manager", None):
                ctx.session_manager = SessionManager(
                    mode="basic",
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )

            if engine == "llm":
                if getattr(ctx.session_manager, "memory_manager", None):
                    ctx.session_manager = SessionManager(
                        mode="llm",
                        project_context=project_context,
                        metadata_manager=metadata_manager,
                    )
                else:
                    ctx.session_manager.mode = "llm"
                ctx.llm_memory = ctx.llm_memory or LLMMemory(
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )
                ctx.basic_checkpointer = None
                ctx.deep_checkpointer = None
                ctx.memory_sync = None
                ctx.global_memory = None

                # Preserve restored session if valid, else load recent/new
                if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode="llm"):
                    logger.info("Keeping user-selected LLM session: %s", ctx.session_id)
                    ctx.console.print(f"[dim]Kept current LLM session: {ctx.session_id}[/]")
                else:
                    recent_session = ctx.session_manager.get_most_recent_session(mode="llm")
                    if recent_session:
                        ctx.session_id = recent_session["session_id"]
                        logger.info("Loaded recent LLM session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Loaded recent llm session: {ctx.session_id}[/]")
                    else:
                        ctx.session_id = ctx.session_manager.create_new_session()
                        logger.info("Created new LLM session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Created new llm session: {ctx.session_id}[/]")

            elif engine == "agent" and agent_type == "basic":
                if getattr(ctx.session_manager, "memory_manager", None):
                    ctx.session_manager = SessionManager(
                        mode="basic",
                        project_context=project_context,
                        metadata_manager=metadata_manager,
                    )
                else:
                    ctx.session_manager.mode = "basic"
                ctx.basic_checkpointer = ctx.basic_checkpointer or BasicAgentCheckpointer(
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )
                ctx.llm_memory = ctx.llm_memory or LLMMemory(
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )
                ctx.deep_checkpointer = None
                ctx.memory_sync = None
                ctx.global_memory = None

                if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode="basic"):
                    logger.info("Keeping user-selected basic session: %s", ctx.session_id)
                    ctx.console.print(f"[dim]Kept current basic session: {ctx.session_id}[/]")
                else:
                    recent_session = ctx.session_manager.get_most_recent_session(mode="basic")
                    if recent_session:
                        ctx.session_id = recent_session["session_id"]
                        logger.info("Loaded recent basic session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Loaded recent basic session: {ctx.session_id}[/]")
                    else:
                        ctx.session_id = ctx.session_manager.create_new_session()
                        logger.info("Created new basic session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Created new basic session: {ctx.session_id}[/]")

            elif engine == "agent" and agent_type == "deep":
                ctx.session_manager = SessionManager(
                    mode="deep",
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )
                ctx.deep_checkpointer = ctx.deep_checkpointer or DeepAgentCheckpointer(
                    project_context=project_context,
                    metadata_manager=metadata_manager,
                )
                ctx.basic_checkpointer = None
                ctx.llm_memory = None
                ctx.global_memory = None
                ctx.memory_sync = None

                if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode="deep"):
                    logger.info("Keeping user-selected deep session: %s", ctx.session_id)
                    ctx.console.print(f"[dim]Kept current deep session: {ctx.session_id}[/]")
                else:
                    recent_session = ctx.session_manager.get_most_recent_session(mode="deep")
                    if recent_session:
                        ctx.session_id = recent_session["session_id"]
                        logger.info("Loaded recent deep session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Loaded recent deep session: {ctx.session_id}[/]")
                    else:
                        ctx.session_id = ctx.session_manager.create_new_session()
                        logger.info("Created new deep session: %s", ctx.session_id)
                        ctx.console.print(f"[dim]Created new deep session: {ctx.session_id}[/]")

        service = get_current_service(ctx)
        init_result = await service.initialize(ctx)
        return CommandResult(
            type=init_result["type"],
            message=init_result.get("message", ""),
            payload=init_result.get("payload"),
        )


__all__ = ["SwitchEngineCommand"]
