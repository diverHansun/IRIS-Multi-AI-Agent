from __future__ import annotations

from src.application.commands.base import BaseCommand, CommandResult


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
            from src.components.shared.memory import GlobalMemoryManager, SessionManager, MemorySyncAdapter

            # Store basic session_id for potential restoration
            ctx._basic_session_id = ctx.session_id

            # Create deep mode memory system
            deep_global_memory = GlobalMemoryManager(agent_mode="deep", max_messages=50)
            deep_session_manager = SessionManager(deep_global_memory)
            deep_memory_sync = MemorySyncAdapter(deep_global_memory, agent_mode="deep")

            # Switch to deep mode session
            # Try to find existing deep session or create new one
            deep_sessions = deep_global_memory.list_sessions()
            if deep_sessions:
                # Use most recent deep session
                ctx.session_id = deep_sessions[0]["session_id"]
                ctx.console.print(f"[dim]Restored deep mode session: {ctx.session_id}[/]")
            else:
                # Create new deep session
                ctx.session_id = deep_session_manager.create_new_session()
                ctx.console.print(f"[dim]Created new deep mode session: {ctx.session_id}[/]")

            # Update context to use deep memory
            ctx.global_memory = deep_global_memory
            ctx.session_manager = deep_session_manager
            ctx.memory_sync = deep_memory_sync

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
                import logging
                logging.warning("Failed to initialize deep agent on mode switch: %s", exc)
                return CommandResult.success(
                    "Switched to deep agent mode. Agent will be initialized on first use."
                )

        # Switch back to basic/llm mode memory system
        from src.components.shared.memory import GlobalMemoryManager, SessionManager, MemorySyncAdapter

        # Restore basic mode memory system
        basic_global_memory = GlobalMemoryManager(agent_mode="basic", max_messages=50)
        basic_session_manager = SessionManager(basic_global_memory)
        basic_memory_sync = MemorySyncAdapter(basic_global_memory, agent_mode="basic")

        # Restore basic session_id if available, otherwise use most recent
        if hasattr(ctx, "_basic_session_id") and ctx._basic_session_id:
            ctx.session_id = ctx._basic_session_id
            ctx.console.print(f"[dim]Restored basic mode session: {ctx.session_id}[/]")
        else:
            # Try to find existing basic session or create new one
            basic_sessions = basic_global_memory.list_sessions()
            if basic_sessions:
                ctx.session_id = basic_sessions[0]["session_id"]
                ctx.console.print(f"[dim]Restored basic mode session: {ctx.session_id}[/]")
            else:
                ctx.session_id = basic_session_manager.create_new_session()
                ctx.console.print(f"[dim]Created new basic mode session: {ctx.session_id}[/]")

        # Update context to use basic memory
        ctx.global_memory = basic_global_memory
        ctx.session_manager = basic_session_manager
        ctx.memory_sync = basic_memory_sync

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
            import logging
            logging.warning("Failed to initialize basic agent on mode switch: %s", exc)
            return CommandResult.success(
                "Switched to basic agent mode. Agent will be initialized on first use."
            )


__all__ = ["ModeCommand"]
