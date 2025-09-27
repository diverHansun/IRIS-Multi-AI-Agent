"""
Connector control commands for CLI
"""

import asyncio
from typing import Dict, Any, List
from ..tools.connector import ConnectorToolManager
from ..tools.connector.crawl4ai.client import Crawl4AIClient
from ..tools.connector.crawl4ai.config import Crawl4AIConfig


async def connector_status(verbose: bool = False):
    """
    Check the status of the Crawl4AI connector service
    """
    try:
        config = Crawl4AIConfig()
        async with Crawl4AIClient(config) as client:
            is_healthy = await client.health_check()
            
            status_info = {
                "service": "Crawl4AI",
                "base_url": config.base_url,
                "status": "healthy" if is_healthy else "unhealthy",
                "timeout": config.timeout,
                "stream_timeout": config.stream_timeout
            }
            
            if verbose:
                try:
                    schema = await client.get_schema()
                    status_info["schema"] = schema
                except Exception as e:
                    status_info["schema_error"] = str(e)
            
            tool_manager = ConnectorToolManager()
            status_info["tool_count"] = tool_manager.get_tool_count()
            
            status_text = f"Crawl4AI connector: {'✓' if is_healthy else '✗'}\n"
            status_text += f"Base URL: {config.base_url}\n"
            status_text += f"Status: {status_info['status']}\n"
            status_text += f"Tools: {status_info['tool_count']} registered\n"
            
            return {
                "type": "status",
                "message": status_text,
                "payload": status_info
            }
    except Exception as e:
        error_msg = f"Failed to check connector status: {str(e)}"
        return {
            "type": "error",
            "message": error_msg,
            "payload": {"error": str(e)}
        }


async def connector_tools(json_flag: bool = False):
    """
    List all registered connector tools
    """
    try:
        manager = ConnectorToolManager()
        tools_info = manager.get_tools_info()
        
        if json_flag:
            # Return JSON format
            return {
                "type": "list",
                "message": "",
                "payload": {
                    "tools": tools_info,
                    "json_flag": json_flag
                }
            }
        else:
            # Return formatted text
            if not tools_info:
                tools_text = "No connector tools registered."
            else:
                tools_text = f"Connector Tools ({len(tools_info)}):\n"
                for name, description in tools_info.items():
                    tools_text += f"  - {name}: {description}\n"
            
            return {
                "type": "list",
                "message": tools_text,
                "payload": {
                    "tools": tools_info,
                    "json_flag": json_flag
                }
            }
    except Exception as e:
        error_msg = f"Failed to list connector tools: {str(e)}"
        return {
            "type": "error",
            "message": error_msg,
            "payload": {"error": str(e)}
        }


async def connector_reload():
    """
    Reload connector tools and refresh connections
    """
    try:
        # Reload tools
        manager = ConnectorToolManager()
        reload_result = manager.reload_tools()

        if not reload_result["success"]:
            return {
                "type": "error",
                "message": reload_result["message"],
                "payload": {"error": reload_result.get("error", "Unknown error")}
            }

        # Test connection after reload
        config = Crawl4AIConfig()
        connection_status = "unknown"
        try:
            async with Crawl4AIClient(config) as client:
                is_healthy = await client.health_check()
                connection_status = "healthy" if is_healthy else "unhealthy"
        except Exception as e:
            connection_status = f"error: {str(e)}"

        reload_info = {
            "old_count": reload_result["old_count"],
            "new_count": reload_result["new_count"],
            "connection_status": connection_status,
            "base_url": config.base_url
        }

        reload_text = f"Connector tools reloaded successfully\n"
        reload_text += f"Tools: {reload_result['old_count']} → {reload_result['new_count']}\n"
        reload_text += f"Connection: {connection_status}\n"
        reload_text += f"Base URL: {config.base_url}\n"

        return {
            "type": "success",
            "message": reload_text,
            "payload": reload_info
        }
    except Exception as e:
        error_msg = f"Failed to reload connector: {str(e)}"
        return {
            "type": "error",
            "message": error_msg,
            "payload": {"error": str(e)}
        }