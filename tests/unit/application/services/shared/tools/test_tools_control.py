from __future__ import annotations

import asyncio

from src.application.services.shared.tools import tools_control


class _Tool:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description


class _ManagerOk:
    def __init__(self, auto_register_defaults: bool = True) -> None:
        assert auto_register_defaults is True

    async def initialize_all(self):
        return None

    def get_status(self):
        return {
            "providers": {
                "sdk": {"initialized": True},
                "mcp": {"initialized": True},
                "connector": {"initialized": True},
            }
        }

    def list_providers(self):
        return ["sdk", "mcp", "connector"]

    def get_tools_by_provider(self, provider_name: str):
        if provider_name == "sdk":
            return [_Tool("search", "Search web"), _Tool("math", "Math helper")]
        return []


class _ManagerInitFail:
    def __init__(self, auto_register_defaults: bool = True) -> None:
        pass

    async def initialize_all(self):
        raise RuntimeError("init failed")


def test_tools_summary_success_with_provider_warnings(monkeypatch):
    monkeypatch.setattr(tools_control, "UnifiedToolManager", _ManagerOk)

    result = asyncio.run(tools_control.tools_summary())

    assert result["type"] == "success"
    payload = result["payload"]
    assert payload["kind"] == "tools_summary"
    assert payload["total"] == 2

    entries = {p["name"]: p for p in payload["providers"]}
    assert entries["sdk"]["display_name"] == "SDK Tools"
    assert entries["mcp"]["warning"] is not None
    assert "No MCP tools available" in entries["mcp"]["warning"]
    assert entries["connector"]["warning"] is not None


def test_tools_list_returns_sorted_rows_and_warnings(monkeypatch):
    monkeypatch.setattr(tools_control, "UnifiedToolManager", _ManagerOk)

    result = asyncio.run(tools_control.tools_list())

    assert result["type"] == "success"
    payload = result["payload"]
    assert payload["kind"] == "tools_list"
    assert payload["total"] == 2
    assert len(payload["warnings"]) == 2
    assert payload["tools"][0]["name"] == "math"
    assert payload["tools"][1]["name"] == "search"


def test_tools_summary_returns_error_when_manager_init_fails(monkeypatch):
    monkeypatch.setattr(tools_control, "UnifiedToolManager", _ManagerInitFail)

    result = asyncio.run(tools_control.tools_summary())

    assert result["type"] == "error"
    assert "Failed to initialize tool providers" in result["message"]
