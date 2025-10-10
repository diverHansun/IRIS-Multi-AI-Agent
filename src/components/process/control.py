"""
Control module for the Multi-AI-Agent project.
This module contains general control commands.
"""

from src.agents.langchain.agent_factory import agent_factory
from src.llm.langchain.llm_manager import reload_llm_config


async def switch_llm(ctx, provider: str, model: str = None):
    """Switch LLM provider/model"""
    try:
        # Validate provider
        available_providers = [p["provider"] for p in agent_factory.get_available_configurations()["available_providers"]]
        if provider not in available_providers:
            return {
                "type": "error",
                "message": f"Unsupported LLM provider: {provider}",
                "payload": {
                    "available_providers": available_providers
                }
            }
        
        # Create new Agent and pass global memory manager
        new_agent = await agent_factory.create_agent(
            provider=provider,
            model=model,
            verbose=True,
            temperature=0.1,
            use_cache=False,  # Don't use cache when switching
            global_memory_manager=ctx.global_memory  # Pass global memory manager
        )
        
        # Get Agent info
        info = new_agent.get_info()
        ctx.console.print(f"[green]Successfully switched to {info['provider']} / {info['model']}[/]")
        ctx.console.print(f"[dim]Tool count: {info['tool_count']}, Memory: {'Enabled' if info['memory_enabled'] else 'Disabled'}[/]")
        ctx.console.print(f"[dim]Memory continuity maintained, you can continue previous conversations after switching[/]")
        
        # Update context
        ctx.agent = new_agent
        
        return {
            "type": "success",
            "message": f"Successfully switched to {info['provider']} / {info['model']}",
            "payload": info
        }
        
    except Exception as e:
        return {
            "type": "error",
            "message": f"Failed to switch LLM: {str(e)}",
            "payload": {}
        }


def set_mode(ctx, mode: str):
    """Set working mode (llm/agent)"""
    if mode.lower() in ["llm", "stream"]:
        ctx.llm_mode = True
        ctx.streaming_enabled = True
        return {
            "type": "success",
            "message": "Switched to LLM mode (streaming output)",
            "payload": {
                "llm_mode": True,
                "streaming_enabled": True
            }
        }
    elif mode.lower() in ["agent", "tool"]:
        ctx.llm_mode = False
        return {
            "type": "success",
            "message": "Switched to Agent mode (tool calling)",
            "payload": {
                "llm_mode": False,
                "streaming_enabled": ctx.streaming_enabled
            }
        }
    else:
        return {
            "type": "error",
            "message": "Invalid mode, please use 'llm' or 'agent'",
            "payload": {}
        }


def set_stream(ctx, action: str):
    """Set streaming output on/off"""
    # Only effective in LLM mode
    if not ctx.llm_mode:
        return {
            "type": "error",
            "message": "Streaming output is only available in LLM mode, please switch to LLM mode first",
            "payload": {}
        }
    
    if action.lower() in ["on", "enable"]:
        ctx.streaming_enabled = True
        return {
            "type": "success",
            "message": "LLM streaming output enabled",
            "payload": {
                "streaming_enabled": True
            }
        }
    elif action.lower() in ["off", "disable"]:
        ctx.streaming_enabled = False
        return {
            "type": "success",
            "message": "LLM streaming output disabled",
            "payload": {
                "streaming_enabled": False
            }
        }
    else:
        return {
            "type": "error",
            "message": "Invalid action, please use 'on' or 'off'",
            "payload": {}
        }


def get_info(ctx):
    """Get system information"""
    agent_info = ctx.agent.get_info()
    
    # Add mode information
    mode_info = {
        "llm_mode": ctx.llm_mode,
        "streaming_enabled": ctx.streaming_enabled,
        "session_id": ctx.session_id
    }
    
    return {
        "type": "info",
        "message": "System information retrieved",
        "payload": {
            "agent": agent_info,
            "mode": mode_info
        }
    }


def reload_config(ctx):
    """Reload LLM configuration from JSON files"""
    try:
        success = reload_llm_config()
        
        if success:
            # Clear agent factory cache to use new config
            agent_factory.clear_cache()
            
            return {
                "type": "success",
                "message": "LLM configuration reloaded successfully",
                "payload": {
                    "cache_cleared": True,
                    "note": "You may need to switch models to use the updated configuration"
                }
            }
        else:
            return {
                "type": "error",
                "message": "Failed to reload LLM configuration",
                "payload": {}
            }
            
    except Exception as e:
        return {
            "type": "error",
            "message": f"Error reloading configuration: {str(e)}",
            "payload": {}
        }