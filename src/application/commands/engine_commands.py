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
        # LLM and basic agent modes share storage, deep mode is isolated
        if engine in ("llm", "agent"):
            # Determine agent_mode based on engine and agent config
            agent_config = ctx.get_engine_config("agent")
            agent_type = agent_config.get("agent_type", "basic")
            
            if engine == "llm" or agent_type == "basic":
                # Use shared storage for LLM and basic agent
                new_mode = "llm" if engine == "llm" else "basic"
                
                # Update existing memory manager and session manager modes
                if hasattr(ctx, "global_memory") and ctx.global_memory:
                    ctx.global_memory.agent_mode = new_mode
                if hasattr(ctx, "session_manager") and ctx.session_manager:
                    ctx.session_manager.mode = new_mode
                if hasattr(ctx, "memory_sync") and ctx.memory_sync:
                    ctx.memory_sync.agent_mode = new_mode
                
                # Reload session from correct storage
                if hasattr(ctx, "session_manager") and ctx.session_manager:
                    recent_session = ctx.session_manager.get_most_recent_session()
                    if recent_session:
                        ctx.session_id = recent_session["session_id"]
                        ctx.console.print(f"[dim]Loaded recent {new_mode} session: {ctx.session_id}[/]")
        
        service = get_current_service(ctx)
        init_result = await service.initialize(ctx)
        return CommandResult(
            type=init_result["type"],
            message=init_result.get("message", ""),
            payload=init_result.get("payload"),
        )


__all__ = ["SwitchEngineCommand"]
