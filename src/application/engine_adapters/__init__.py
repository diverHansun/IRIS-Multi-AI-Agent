"""Engine adapter router used to dispatch queries to engine services."""

from __future__ import annotations

from typing import Dict, Type

from src.application.engine_adapters.agent_adapter import AgentAdapter
from src.application.engine_adapters.agentflow_adapter import AgentFlowAdapter
from src.application.engine_adapters.base import BaseAdapter
from src.application.engine_adapters.dify_adapter import DifyAdapter
from src.application.engine_adapters.llm_adapter import LLMAdapter


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
