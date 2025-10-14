"""
Connector tool control utilities.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.components.shared.tools.connector import ConnectorToolManager
from src.components.shared.tools.connector.crawl4ai.client import Crawl4AIClient
from src.components.shared.tools.connector.crawl4ai.config import Crawl4AIConfig


async def connector_status(verbose: bool = False) -> Dict[str, Any]:
    """
    Inspect the Crawl4AI connector service.
    """
    try:
        config = Crawl4AIConfig()
        async with Crawl4AIClient(config) as client:
            is_healthy = await client.health_check()
            status: Dict[str, Any] = {
                "service": "Crawl4AI",
                "base_url": config.base_url,
                "status": "healthy" if is_healthy else "unhealthy",
                "timeout": config.timeout,
                "stream_timeout": config.stream_timeout,
            }

            if verbose:
                try:
                    status["schema"] = await client.get_schema()
                except Exception as exc:
                    status["schema_error"] = str(exc)

        manager = ConnectorToolManager()
        status["tool_count"] = manager.get_tool_count()

        message = (
            f"Crawl4AI connector status: {status['status']}\n"
            f"Base URL: {status['base_url']}\n"
            f"Registered tools: {status['tool_count']}"
        )

        return {"type": "success", "message": message, "payload": status}
    except Exception as exc:
        return {
            "type": "error",
            "message": f"Failed to check connector status: {exc}",
            "payload": {"error": str(exc)},
        }


async def connector_tools(json_flag: bool = False) -> Dict[str, Any]:
    """
    Return details about registered connector tools.
    """
    try:
        manager = ConnectorToolManager()
        tools_info: Dict[str, str] = manager.get_tools_info()

        payload = {"tools": tools_info, "json_flag": json_flag}
        if json_flag:
            return {"type": "success", "message": "", "payload": payload}

        if not tools_info:
            message = "No connector tools registered."
        else:
            lines = [f"Connector Tools ({len(tools_info)}):"]
            for name, description in tools_info.items():
                lines.append(f"  - {name}: {description}")
            message = "\n".join(lines)

        return {"type": "success", "message": message, "payload": payload}
    except Exception as exc:
        return {
            "type": "error",
            "message": f"Failed to list connector tools: {exc}",
            "payload": {"error": str(exc)},
        }


async def connector_reload() -> Dict[str, Any]:
    """
    Reload connector tools and verify the connector health.
    """
    try:
        manager = ConnectorToolManager()
        reload_result = manager.reload_tools()

        if not reload_result.get("success", False):
            return {
                "type": "error",
                "message": reload_result.get("message", "Reload failed."),
                "payload": {"error": reload_result.get("error", "Unknown error.")},
            }

        config = Crawl4AIConfig()
        connection_status = "unknown"
        try:
            async with Crawl4AIClient(config) as client:
                is_healthy = await client.health_check()
                connection_status = "healthy" if is_healthy else "unhealthy"
        except Exception as exc:
            connection_status = f"error: {exc}"

        payload = {
            "old_count": reload_result.get("old_count"),
            "new_count": reload_result.get("new_count"),
            "connection_status": connection_status,
            "base_url": config.base_url,
        }
        message = (
            "Connector tools reloaded successfully.\n"
            f"Tools: {payload['old_count']} -> {payload['new_count']}\n"
            f"Connection status: {connection_status}\n"
            f"Base URL: {config.base_url}"
        )

        return {"type": "success", "message": message, "payload": payload}
    except Exception as exc:
        return {
            "type": "error",
            "message": f"Failed to reload connector tools: {exc}",
            "payload": {"error": str(exc)},
        }

