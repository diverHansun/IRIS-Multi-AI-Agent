"""
Tools control utilities for the /tools command.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from src.components.shared.tools.unified_manager import UnifiedToolManager


@dataclass(slots=True)
class ProviderTools:
    name: str
    display_name: str
    tools: List[BaseTool]
    warning: Optional[str] = None


PROVIDER_LABELS: Dict[str, str] = {
    "sdk": "SDK Tools",
    "mcp": "MCP Tools",
    "connector": "Connector Tools",
}


async def _load_providers() -> Dict[str, ProviderTools]:
    manager = UnifiedToolManager(auto_register_defaults=True)

    try:
        await manager.initialize_all()
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize tool providers: {exc}") from exc

    provider_status = manager.get_status().get("providers", {})
    providers: Dict[str, ProviderTools] = {}

    for provider_name in manager.list_providers():
        warning: Optional[str] = None
        tools: List[BaseTool]

        try:
            provider_tools = manager.get_tools_by_provider(provider_name)
            tools = list(provider_tools) if provider_tools else []
        except Exception as exc:  # pragma: no cover - defensive path
            tools = []
            warning = f"Unable to load tools for provider '{provider_name}': {exc}"

        status_info = provider_status.get(provider_name, {})
        if not status_info.get("initialized", True):
            warning = warning or "Provider was not initialized."
        elif not tools:
            if provider_name == "mcp":
                warning = warning or "No MCP tools available. Check MCP configuration and dependencies."
            elif provider_name == "connector":
                warning = warning or "No connector tools available. Ensure connector services are running."

        providers[provider_name] = ProviderTools(
            name=provider_name,
            display_name=PROVIDER_LABELS.get(provider_name, provider_name.title()),
            tools=tools,
            warning=warning,
        )

    return providers


async def tools_summary() -> Dict[str, Any]:
    try:
        providers = await _load_providers()
    except RuntimeError as exc:
        message = str(exc)
        return {
            "type": "error",
            "message": message,
            "payload": {"error": message},
        }

    total = sum(len(info.tools) for info in providers.values())

    summary_entries: List[Dict[str, Any]] = []
    for provider in providers.values():
        sample_names = [tool.name for tool in provider.tools[:5]]
        summary_entries.append(
            {
                "name": provider.name,
                "display_name": provider.display_name,
                "count": len(provider.tools),
                "samples": sample_names,
                "warning": provider.warning,
            }
        )

    return {
        "type": "success",
        "message": "",
        "payload": {
            "kind": "tools_summary",
            "total": total,
            "providers": summary_entries,
        },
    }


async def tools_list() -> Dict[str, Any]:
    try:
        providers = await _load_providers()
    except RuntimeError as exc:
        message = str(exc)
        return {
            "type": "error",
            "message": message,
            "payload": {"error": message},
        }

    rows: List[Dict[str, str]] = []
    warnings: List[str] = []

    for provider in providers.values():
        if provider.warning:
            warnings.append(provider.warning)

        for tool in provider.tools:
            rows.append(
                {
                    "name": getattr(tool, "name", "unknown"),
                    "provider": provider.display_name,
                    "description": getattr(tool, "description", "") or "",
                }
            )

    rows.sort(key=lambda item: (item["provider"], item["name"]))

    return {
        "type": "success",
        "message": "",
        "payload": {
            "kind": "tools_list",
            "tools": rows,
            "warnings": warnings,
            "total": len(rows),
        },
    }


__all__ = ["tools_summary", "tools_list"]
