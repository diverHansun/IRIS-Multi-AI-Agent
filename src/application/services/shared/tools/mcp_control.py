"""
MCP tool control utilities used by command handlers.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from src.components.shared.tools.mcp import GlobalMCPManager

    MCP_AVAILABLE = True
except Exception:  # pragma: no cover - MCP is optional
    GlobalMCPManager = None
    MCP_AVAILABLE = False


def _unavailable_response() -> Dict[str, Any]:
    return {
        "type": "error",
        "message": "MCP manager is not available. Ensure the MCP dependencies are installed and configured.",
        "payload": {},
    }


async def mcp_status(verbose: bool = False) -> Dict[str, Any]:
    """
    Return the current MCP status information.
    """
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return _unavailable_response()

    try:
        await GlobalMCPManager.initialize()
    except Exception as exc:
        return {
            "type": "error",
            "message": f"MCP initialisation failed: {exc}",
            "payload": {},
        }

    status = GlobalMCPManager.get_status(verbose=verbose)
    return {
        "type": "success",
        "message": "MCP status retrieved.",
        "payload": status,
    }


async def mcp_tools(json_flag: bool = False) -> Dict[str, Any]:
    """
    List registered MCP tools.
    """
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return _unavailable_response()

    try:
        await GlobalMCPManager.initialize()
    except Exception as exc:
        return {
            "type": "error",
            "message": f"MCP initialisation failed: {exc}",
            "payload": {},
        }

    tools: List[Dict[str, Any]] = GlobalMCPManager.get_tools()
    return {
        "type": "success",
        "message": f"{len(tools)} MCP tool(s) loaded.",
        "payload": {"tools": tools, "json_flag": json_flag},
    }


async def mcp_reload() -> Dict[str, Any]:
    """
    Reload MCP configuration and tool definitions.
    """
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return _unavailable_response()

    try:
        result = await GlobalMCPManager.reload_config()
        return {
            "type": "success",
            "message": "MCP configuration reloaded.",
            "payload": result,
        }
    except Exception as exc:
        return {
            "type": "error",
            "message": f"Failed to reload MCP configuration: {exc}",
            "payload": {},
        }

