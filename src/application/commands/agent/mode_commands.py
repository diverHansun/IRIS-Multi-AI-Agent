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
                # Use ZHIPU/glm-4.6 as default if available
                if "ZHIPU" in providers:
                    zhipu_models = providers["ZHIPU"].get("models", {})
                    if "glm-4.6" in zhipu_models:
                        config["provider"] = "ZHIPU"
                        config["model"] = "glm-4.6"
                    else:
                        # Use first available ZHIPU model
                        if zhipu_models:
                            first_model = next(iter(zhipu_models.keys()))
                            config["provider"] = "ZHIPU"
                            config["model"] = first_model
                else:
                    # Fallback to first available provider/model
                    first_provider = next(iter(providers.keys()))
                    first_provider_models = providers[first_provider].get("models", {})
                    if first_provider_models:
                        first_model = next(iter(first_provider_models.keys()))
                        config["provider"] = first_provider
                        config["model"] = first_model

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

        return CommandResult.success("Switched to basic agent mode.")


__all__ = ["ModeCommand"]
