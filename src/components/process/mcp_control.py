"""
MCP control module for the Multi-AI-Agent project.
This module contains MCP management commands.
"""

# Try to import MCP manager
try:
    from src.tools.mcp import GlobalMCPManager
    MCP_AVAILABLE = True
except Exception:
    GlobalMCPManager = None
    MCP_AVAILABLE = False


async def mcp_status(verbose: bool = False):
    """Get MCP status"""
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return {
            "type": "error",
            "message": "MCP manager is not available (missing dependencies or not integrated)",
            "payload": {}
        }
    
    try:
        # Ensure initialized (respect config)
        await GlobalMCPManager.initialize()
    except Exception as e:
        return {
            "type": "error",
            "message": f"MCP initialization failed: {e}",
            "payload": {}
        }
    
    status = GlobalMCPManager.get_status(verbose=verbose)
    return {
        "type": "status",
        "message": "MCP status retrieved",
        "payload": status
    }


async def mcp_tools(json_flag: bool = False):
    """List MCP tools"""
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return {
            "type": "error",
            "message": "MCP manager is not available (missing dependencies or not integrated)",
            "payload": {}
        }
    
    try:
        # Ensure initialized (respect config)
        await GlobalMCPManager.initialize()
    except Exception as e:
        return {
            "type": "error",
            "message": f"MCP initialization failed: {e}",
            "payload": {}
        }
    
    tools = GlobalMCPManager.get_tools()
    return {
        "type": "list",
        "message": f"Found {len(tools)} MCP tools",
        "payload": {
            "tools": tools,
            "json_flag": json_flag
        }
    }


async def mcp_reload():
    """Reload MCP configuration"""
    if not MCP_AVAILABLE or GlobalMCPManager is None:
        return {
            "type": "error",
            "message": "MCP manager is not available (missing dependencies or not integrated)",
            "payload": {}
        }
    
    try:
        result = await GlobalMCPManager.reload_config()
        return {
            "type": "success",
            "message": "MCP configuration reloaded",
            "payload": result
        }
    except Exception as e:
        return {
            "type": "error",
            "message": f"Failed to reload MCP configuration: {e}",
            "payload": {}
        }