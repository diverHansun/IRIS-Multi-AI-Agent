"""Engine adapter router used to dispatch queries to engine services."""

from __future__ import annotations

from typing import Dict, Type

from .agent_adapter import AgentAdapter
from .agentflow_adapter import AgentFlowAdapter
from .base import BaseAdapter
from .dify_adapter import DifyAdapter
from .llm_adapter import LLMAdapter


ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "llm": LLMAdapter,
    "agent": AgentAdapter,
    "agentflow": AgentFlowAdapter,
    "dify": DifyAdapter,
}


def get_adapter(engine: str) -> BaseAdapter:
    if engine not in ADAPTERS:
        raise ValueError(f"Unknown engine '{engine}'")
    adapter_cls = ADAPTERS[engine]
    return adapter_cls()
