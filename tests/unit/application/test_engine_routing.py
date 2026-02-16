from unittest.mock import MagicMock

import pytest

from src.application.engine_adapters import get_adapter
from src.application.engine_adapters.agent_adapter import AgentAdapter
from src.application.engine_adapters.agentflow_adapter import AgentFlowAdapter
from src.application.engine_adapters.dify_adapter import DifyAdapter
from src.application.engine_adapters.llm_adapter import LLMAdapter
from src.application.services import get_current_service
from src.application.services.agent.basic import BasicAgentService
from src.application.services.agent.deep import DeepAgentService
from src.application.services.agentflow import AgentFlowService
from src.application.services.dify.service import DifyService
from src.application.services.llm import LLMService


class _DummyCtx:
    def __init__(self, current_engine: str, agent_type: str = "basic") -> None:
        self.current_engine = current_engine
        self.session_id = "session-1"
        self.console = MagicMock()
        self._configs = {
            "agent": {"agent_type": agent_type},
            "llm": {},
            "dify": {},
            "agentflow": {},
        }

    def get_engine_config(self, engine: str):
        return self._configs.setdefault(engine, {})


def test_get_adapter_returns_expected_adapter_instances():
    assert isinstance(get_adapter("llm"), LLMAdapter)
    assert isinstance(get_adapter("agent"), AgentAdapter)
    assert isinstance(get_adapter("agentflow"), AgentFlowAdapter)
    assert isinstance(get_adapter("dify"), DifyAdapter)


def test_get_adapter_raises_for_unknown_engine():
    with pytest.raises(ValueError, match="Unknown engine"):
        get_adapter("unknown")


def test_get_current_service_routes_llm():
    service = get_current_service(_DummyCtx("llm"))
    assert isinstance(service, LLMService)


def test_get_current_service_routes_agent_basic():
    service = get_current_service(_DummyCtx("agent", agent_type="basic"))
    assert isinstance(service, BasicAgentService)


def test_get_current_service_routes_agent_deep():
    service = get_current_service(_DummyCtx("agent", agent_type="deep"))
    assert isinstance(service, DeepAgentService)


def test_get_current_service_routes_agentflow():
    service = get_current_service(_DummyCtx("agentflow"))
    assert isinstance(service, AgentFlowService)


def test_get_current_service_routes_dify():
    service = get_current_service(_DummyCtx("dify"))
    assert isinstance(service, DifyService)


def test_get_current_service_rejects_unknown_agent_type():
    with pytest.raises(ValueError, match="Unknown agent type"):
        get_current_service(_DummyCtx("agent", agent_type="custom"))


def test_get_current_service_rejects_unknown_engine():
    with pytest.raises(ValueError, match="Unknown engine"):
        get_current_service(_DummyCtx("unsupported"))
