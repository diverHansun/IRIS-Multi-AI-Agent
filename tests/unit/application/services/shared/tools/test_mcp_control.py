from __future__ import annotations

import asyncio

from src.application.services.shared.tools import mcp_control


class _ManagerOk:
    @staticmethod
    async def initialize():
        return None

    @staticmethod
    def get_status(verbose: bool = False):
        return {"ok": True, "verbose": verbose}

    @staticmethod
    def get_tools():
        return [{"name": "tool-a"}, {"name": "tool-b"}]

    @staticmethod
    async def reload_config():
        return {"reloaded": True}


class _ManagerInitFail:
    @staticmethod
    async def initialize():
        raise RuntimeError("init boom")


def test_mcp_status_returns_unavailable_when_manager_missing(monkeypatch):
    monkeypatch.setattr(mcp_control, "MCP_AVAILABLE", False)
    monkeypatch.setattr(mcp_control, "GlobalMCPManager", None)

    result = asyncio.run(mcp_control.mcp_status())

    assert result["type"] == "error"
    assert "MCP manager is not available" in result["message"]


def test_mcp_status_handles_initialization_failure(monkeypatch):
    monkeypatch.setattr(mcp_control, "MCP_AVAILABLE", True)
    monkeypatch.setattr(mcp_control, "GlobalMCPManager", _ManagerInitFail)

    result = asyncio.run(mcp_control.mcp_status(verbose=True))

    assert result["type"] == "error"
    assert "MCP initialisation failed" in result["message"]


def test_mcp_status_success(monkeypatch):
    monkeypatch.setattr(mcp_control, "MCP_AVAILABLE", True)
    monkeypatch.setattr(mcp_control, "GlobalMCPManager", _ManagerOk)

    result = asyncio.run(mcp_control.mcp_status(verbose=True))

    assert result["type"] == "success"
    assert result["payload"] == {"ok": True, "verbose": True}


def test_mcp_tools_success(monkeypatch):
    monkeypatch.setattr(mcp_control, "MCP_AVAILABLE", True)
    monkeypatch.setattr(mcp_control, "GlobalMCPManager", _ManagerOk)

    result = asyncio.run(mcp_control.mcp_tools(json_flag=True))

    assert result["type"] == "success"
    assert result["payload"]["json_flag"] is True
    assert len(result["payload"]["tools"]) == 2


def test_mcp_reload_success_and_failure(monkeypatch):
    monkeypatch.setattr(mcp_control, "MCP_AVAILABLE", True)
    monkeypatch.setattr(mcp_control, "GlobalMCPManager", _ManagerOk)

    success = asyncio.run(mcp_control.mcp_reload())
    assert success["type"] == "success"
    assert success["payload"] == {"reloaded": True}

    class _ManagerReloadFail:
        @staticmethod
        async def reload_config():
            raise RuntimeError("reload failed")

    monkeypatch.setattr(mcp_control, "GlobalMCPManager", _ManagerReloadFail)
    failed = asyncio.run(mcp_control.mcp_reload())
    assert failed["type"] == "error"
    assert "Failed to reload MCP configuration" in failed["message"]
