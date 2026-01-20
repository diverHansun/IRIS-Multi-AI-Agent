from __future__ import annotations

import logging

from src.application.commands.base import BaseCommand, CommandResult

logger = logging.getLogger(__name__)


class ModeCommand(BaseCommand):
    name = "mode"
    engine_scope = ("agent",)
    help_text = "Switch between basic and deep agent modes."

    async def execute(self, ctx, args: str) -> CommandResult:
        target = args.strip().lower()
        config = ctx.get_engine_config("agent")
        current = config.get("agent_type", "basic")

        if not target:
            return CommandResult.info(f"Current agent mode: {current}")

        if target not in {"basic", "deep"}:
            return CommandResult.error("Usage: /mode <basic|deep>")

        if target == current:
            return CommandResult.info(f"Agent mode already set to {target}.")

        config["agent_type"] = target
        config["agent_instance"] = None

        if target == "deep":
            # Set default function type
            config.setdefault("function_type", "research")

            # Load default provider and model from providers.json
            from src.core.providers import deepagents_provider_registry
            from src.components.shared.memory import SessionManager, DeepAgentCheckpointer

            providers = deepagents_provider_registry.list_providers()
            if providers:
                # Use zhipu/glm-4.6 as default if available
                if "zhipu" in providers:
                    zhipu_models = providers["zhipu"].get("models", {})
                    if "glm-4.6" in zhipu_models:
                        config["provider"] = "zhipu"
                        config["model"] = "glm-4.6"
                    else:
                        # Use first available zhipu model
                        if zhipu_models:
                            first_model = next(iter(zhipu_models.keys()))
                            config["provider"] = "zhipu"
                            config["model"] = first_model
                else:
                    # Fallback to first available provider/model
                    first_provider = next(iter(providers.keys()))
                    first_provider_models = providers[first_provider].get("models", {})
                    if first_provider_models:
                        first_model = next(iter(first_provider_models.keys()))
                        config["provider"] = first_provider
                        config["model"] = first_model

            # Switch to deep mode memory system
            import logging

            logger = logging.getLogger(__name__)

            ctx._basic_session_id = ctx.session_id

            project_context = getattr(ctx, "project_context", None)
            metadata_manager = getattr(ctx, "metadata_manager", None)

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
            ctx.memory_sync = None
            ctx.global_memory = None

            recent_session = ctx.session_manager.get_most_recent_session(mode="deep")
            if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode="deep"):
                logger.info("Restored user-selected deep session: %s", ctx.session_id)
                ctx.console.print(f"[dim]Restored deep mode session: {ctx.session_id}[/]")
            elif recent_session:
                ctx.session_id = recent_session["session_id"]
                logger.info("Restored deep mode session: %s", ctx.session_id)
                ctx.console.print(f"[dim]Restored deep mode session: {ctx.session_id}[/]")
            else:
                ctx.session_id = ctx.session_manager.create_new_session()
                logger.info("Created new deep mode session: %s", ctx.session_id)
                ctx.console.print(f"[dim]Created new deep mode session: {ctx.session_id}[/]")

            # Initialize default deep agent immediately for better UX
            from src.application.services.agent.deep.agent_lifecycle import create_default_deep_agent

            try:
                agent, info = await create_default_deep_agent(ctx, target="deep")
                config["agent_instance"] = agent
                provider = info.get("provider", config.get("provider", "unknown"))
                model = info.get("model", config.get("model", "unknown"))
                function_type = info.get("function_type", config.get("function_type", "research"))
                tool_count = info.get("tool_count", 0)

                return CommandResult.success(
                    f"Switched to deep agent mode. Agent initialized: {provider}/{model} (function: {function_type}, tools: {tool_count})"
                )
            except Exception as exc:
                # If agent creation fails, still allow mode switch but show warning
                logger.warning("Failed to initialize deep agent on mode switch: %s", exc)
                return CommandResult.success(
                    "Switched to deep agent mode. Agent will be initialized on first use."
                )

        # Switch back to basic/llm mode memory system
        from src.components.shared.memory import SessionManager, BasicAgentCheckpointer, LLMMemory

        if not getattr(ctx, "session_manager", None) or getattr(ctx.session_manager, "memory_manager", None):
            ctx.session_manager = SessionManager(
                mode="basic",
                project_context=getattr(ctx, "project_context", None),
                metadata_manager=getattr(ctx, "metadata_manager", None),
            )
        else:
            ctx.session_manager.mode = "basic"

        ctx.basic_checkpointer = ctx.basic_checkpointer or BasicAgentCheckpointer(
            project_context=getattr(ctx, "project_context", None),
            metadata_manager=getattr(ctx, "metadata_manager", None),
        )
        ctx.llm_memory = ctx.llm_memory or LLMMemory(
            project_context=getattr(ctx, "project_context", None),
            metadata_manager=getattr(ctx, "metadata_manager", None),
        )
        ctx.deep_checkpointer = None
        ctx.memory_sync = None
        ctx.global_memory = None

        if hasattr(ctx, "_basic_session_id") and ctx._basic_session_id and ctx.session_manager.session_exists(ctx._basic_session_id, mode="basic"):
            ctx.session_id = ctx._basic_session_id
            ctx.console.print(f"[dim]Restored basic mode session: {ctx.session_id}[/]")
        else:
            basic_sessions = ctx.session_manager.list_sessions(mode="basic")
            if basic_sessions:
                ctx.session_id = basic_sessions[0]["session_id"]
                ctx.console.print(f"[dim]Restored basic mode session: {ctx.session_id}[/]")
            else:
                ctx.session_id = ctx.session_manager.create_new_session()
                ctx.console.print(f"[dim]Created new basic mode session: {ctx.session_id}[/]")

        # Clean up deep mode specific configurations
        config.pop("function_type", None)
        config.pop("middleware", None)

        # Clear deep mode provider/model to avoid compatibility issues
        # Basic and deep agents may have different model configurations
        config.pop("provider", None)
        config.pop("model", None)

        # Initialize default basic agent immediately for better UX
        from src.application.services.agent.basic.agent_lifecycle import create_default_agent

        try:
            agent, info = await create_default_agent(ctx, target="basic")
            config["agent_instance"] = agent
            provider = info.get("provider", config.get("provider", "unknown"))
            model = info.get("model", config.get("model", "unknown"))
            tool_count = info.get("tool_count", 0)

            return CommandResult.success(
                f"Switched to basic agent mode. Agent initialized: {provider}/{model} (tools: {tool_count})"
            )
        except Exception as exc:
            # If agent creation fails, still allow mode switch but show warning
            logger.warning("Failed to initialize basic agent on mode switch: %s", exc)
            return CommandResult.success(
                "Switched to basic agent mode. Agent will be initialized on first use."
            )


__all__ = ["ModeCommand"]
