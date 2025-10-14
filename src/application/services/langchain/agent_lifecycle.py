"""
Agent lifecycle helpers for LangChain services.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from src.agents.langchain.managers import agent_manager

from .streaming import register_llm


def _langchain_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("langchain")


async def create_default_agent(ctx) -> Tuple[Any, Dict[str, Any]]:
    """
    Create the default LangChain agent and return the instance alongside
    its metadata.
    """
    config = _langchain_config(ctx)
    provider = config.get("provider")
    model = config.get("model")
    agent = await agent_manager.create_agent(
        provider=provider,
        model=model,
        global_memory_manager=ctx.global_memory,
    )

    # Post creation adjustments
    if hasattr(agent, "verbose"):
        agent.verbose = True
    if hasattr(agent, "temperature"):
        agent.temperature = 0.1

    info = agent.get_info() if hasattr(agent, "get_info") else {}
    config["provider"] = info.get("provider", provider)
    config["model"] = info.get("model", model)
    config["agent"] = agent

    if hasattr(agent, "get_llm"):
        llm = agent.get_llm()
        register_llm(config["provider"], llm)

    return agent, info


async def switch_agent(ctx, provider: str, model: str | None = None) -> Tuple[Any, Dict[str, Any]]:
    """
    Switch the active agent to a new provider/model pair and update the
    context configuration accordingly.
    """
    config = _langchain_config(ctx)
    agent = await agent_manager.create_agent(
        provider=provider,
        model=model,
        global_memory_manager=ctx.global_memory,
    )

    if hasattr(agent, "verbose"):
        agent.verbose = True
    if hasattr(agent, "temperature"):
        agent.temperature = 0.1

    info = agent.get_info() if hasattr(agent, "get_info") else {}
    config["provider"] = info.get("provider", provider)
    config["model"] = info.get("model", model)
    config["agent"] = agent

    if hasattr(agent, "get_llm"):
        llm = agent.get_llm()
        register_llm(config["provider"], llm)

    return agent, info

