from __future__ import annotations

import asyncio

from src.application.services.shared.tools import connector_control


class _Config:
    def __init__(self):
        self.base_url = "http://localhost:11235"
        self.timeout = 10
        self.stream_timeout = 20


class _ClientHealthy:
    def __init__(self, config):
        self.config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def health_check(self):
        return True

    async def get_schema(self):
        return {"name": "crawl4ai"}


class _ClientRaises:
    def __init__(self, config):
        self.config = config

    async def __aenter__(self):
        raise RuntimeError("connection failed")

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _Manager:
    def __init__(self):
        pass

    def get_tool_count(self):
        return 2

    def get_tools_info(self):
        return {"crawl": "crawl web pages", "extract": "extract content"}

    def reload_tools(self):
        return {"success": True, "old_count": 1, "new_count": 2}


class _ManagerReloadFail(_Manager):
    def reload_tools(self):
        return {"success": False, "message": "reload failed", "error": "boom"}


def test_connector_status_success_verbose(monkeypatch):
    monkeypatch.setattr(connector_control, "Crawl4AIConfig", _Config)
    monkeypatch.setattr(connector_control, "Crawl4AIClient", _ClientHealthy)
    monkeypatch.setattr(connector_control, "ConnectorToolManager", _Manager)

    result = asyncio.run(connector_control.connector_status(verbose=True))

    assert result["type"] == "success"
    payload = result["payload"]
    assert payload["status"] == "healthy"
    assert payload["tool_count"] == 2
    assert payload["schema"] == {"name": "crawl4ai"}


def test_connector_status_error_when_client_fails(monkeypatch):
    monkeypatch.setattr(connector_control, "Crawl4AIConfig", _Config)
    monkeypatch.setattr(connector_control, "Crawl4AIClient", _ClientRaises)
    monkeypatch.setattr(connector_control, "ConnectorToolManager", _Manager)

    result = asyncio.run(connector_control.connector_status(verbose=False))

    assert result["type"] == "error"
    assert "Failed to check connector status" in result["message"]


def test_connector_tools_render_and_json_modes(monkeypatch):
    monkeypatch.setattr(connector_control, "ConnectorToolManager", _Manager)

    render_result = asyncio.run(connector_control.connector_tools(json_flag=False))
    assert render_result["type"] == "success"
    assert "Connector Tools (2):" in render_result["message"]
    assert "crawl" in render_result["message"]
    assert render_result["payload"]["json_flag"] is False

    json_result = asyncio.run(connector_control.connector_tools(json_flag=True))
    assert json_result["type"] == "success"
    assert json_result["message"] == ""
    assert json_result["payload"]["json_flag"] is True


def test_connector_reload_success_and_reload_failure(monkeypatch):
    monkeypatch.setattr(connector_control, "Crawl4AIConfig", _Config)
    monkeypatch.setattr(connector_control, "Crawl4AIClient", _ClientHealthy)
    monkeypatch.setattr(connector_control, "ConnectorToolManager", _Manager)

    success = asyncio.run(connector_control.connector_reload())
    assert success["type"] == "success"
    assert success["payload"]["old_count"] == 1
    assert success["payload"]["new_count"] == 2
    assert success["payload"]["connection_status"] == "healthy"

    monkeypatch.setattr(connector_control, "ConnectorToolManager", _ManagerReloadFail)
    failed = asyncio.run(connector_control.connector_reload())
    assert failed["type"] == "error"
    assert failed["message"] == "reload failed"
