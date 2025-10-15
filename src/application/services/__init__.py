"""Service router for engine-specific business logic."""

from __future__ import annotations

from .base import BaseEngineService


def get_current_service(ctx) -> BaseEngineService:
    engine = getattr(ctx, "current_engine", None)
    if engine == "llm":
        from .llm import LLMService

        return LLMService()
    if engine == "agent":
        from .agent.basic import BasicAgentService

        agent_type = ctx.get_engine_config("agent").get("agent_type", "basic").lower()
        if agent_type in {"basic", ""}:
            return BasicAgentService()
        raise NotImplementedError("Deep agent mode is not available yet.")
    if engine == "agentflow":
        from .agentflow import AgentFlowService

        return AgentFlowService()
    if engine == "dify":
        from .dify.service import DifyService

        return DifyService()
    raise ValueError(f"Unknown engine '{engine}'")
