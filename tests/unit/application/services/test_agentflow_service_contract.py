import asyncio

import pytest

from src.application.services.agentflow.service import AgentFlowService


class _Ctx:
    session_id = "sess-agentflow"


def test_initialize_reports_not_implemented_info():
    service = AgentFlowService()
    result = asyncio.run(service.initialize(_Ctx()))

    assert result["type"] == "info"
    assert "not implemented" in result["message"].lower()


def test_handle_query_raises_not_implemented():
    service = AgentFlowService()

    with pytest.raises(NotImplementedError, match="not available yet"):
        asyncio.run(service.handle_query(_Ctx(), "query"))


def test_switch_model_returns_error_contract():
    service = AgentFlowService()
    result = asyncio.run(service.switch_model(_Ctx(), "provider", "model"))

    assert result["type"] == "error"
    assert "not available yet" in result["message"]


def test_get_info_reports_pending_status():
    service = AgentFlowService()
    info = service.get_info(_Ctx())

    assert info == {"engine": "agentflow", "status": "pending"}
