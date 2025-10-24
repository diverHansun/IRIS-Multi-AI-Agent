"""Command for selecting deep agent function types."""

from __future__ import annotations

from typing import Dict

from src.agents.deepagents.managers import deep_agent_manager
from src.application.commands.base import BaseCommand, CommandResult
from src.application.services.agent.deep.agent_lifecycle import switch_deep_agent


class UseCommand(BaseCommand):
    name = "use"
    engine_scope = ("agent",)
    help_text = "Select the active deep agent function (research, coding, analysis)."

    async def execute(self, ctx, args: str) -> CommandResult:
        target = args.strip().lower()
        functions = deep_agent_manager.get_available_functions()
        if not target:
            return self._list_functions(functions)

        if target not in functions:
            return CommandResult.error(
                f"Unknown deep agent function '{target}'. Available: {', '.join(functions.keys())}"
            )

        config = ctx.get_engine_config("agent")
        current = config.get("function_type", "research").lower()
        config["function_type"] = target

        if config.get("agent_type", "basic") != "deep":
            return CommandResult.success(
                f"Deep agent function set to {target}. Switch to deep mode to activate.",
                payload={"function_type": target},
            )

        if current == target and config.get("agent_instance"):
            return CommandResult.info(f"Deep agent function already set to {target}.", payload={"function_type": target})

        try:
            agent, info = await switch_deep_agent(
                ctx,
                provider=config.get("provider"),
                model=config.get("model"),
                function_type=target,
                target="deep",
            )
        except ValueError as exc:
            return CommandResult.error(str(exc))

        config["agent_instance"] = agent

        message = f"Deep agent function switched to {target} ({info.get('provider')}/{info.get('model')})."
        return CommandResult.success(
            message,
            payload={
                "function_type": target,
                "agent": info,
            },
        )

    def _list_functions(self, functions: Dict[str, Dict[str, str]]) -> CommandResult:
        lines = [
            f"- {name}: {meta.get('description', '').strip() or 'No description'}"
            for name, meta in functions.items()
        ]
        message = "Available deep agent functions:\n" + "\n".join(lines)
        return CommandResult.info(message, payload={"functions": functions})


__all__ = ["UseCommand"]
