"""
Control module for the Multi-AI-Agent project.
This module contains general control commands.
"""

from src.agents.langchain.managers import agent_manager
from src.llm.langchain.managers import reload_llm_config


async def switch_llm(ctx, provider: str, model: str = None):
    """Switch LLM provider/model"""
    try:
        # Validate provider using new agent manager
        available_providers = [p["provider"] for p in agent_manager.get_available_agents()]
        if provider not in available_providers:
            return {
                "type": "error",
                "message": f"Unsupported LLM provider: {provider}",
                "payload": {
                    "available_providers": available_providers
                }
            }
        
        # Create new Agent and pass global memory manager using new architecture
        new_agent = await agent_manager.create_agent(
            provider=provider,
            model=model,
            use_cache=False,  # Don't use cache when switching
            global_memory_manager=ctx.global_memory  # Pass global memory manager
        )
        # Set specific parameters after agent creation if needed
        if hasattr(new_agent, 'verbose'):
            new_agent.verbose = True
        if hasattr(new_agent, 'temperature'):
            new_agent.temperature = 0.1
        
        # Get Agent info
        info = new_agent.get_info()
        ctx.console.print(f"[green]Successfully switched to {info['provider']} / {info['model']}[/]")
        ctx.console.print(f"[dim]Tool count: {info['tool_count']}, Memory: {'Enabled' if info['memory_enabled'] else 'Disabled'}[/]")
        ctx.console.print(f"[dim]Memory continuity maintained, you can continue previous conversations after switching[/]")
        
        # Update streaming LLM registration for LLM mode
        # This ensures the streaming manager uses the new LLM instance
        if hasattr(new_agent, 'get_llm') and callable(getattr(new_agent, 'get_llm')):
            try:
                from src.llm.langchain.utils import streaming_manager
                llm = new_agent.get_llm()
                if llm:
                    # Re-register the provider with new LLM instance
                    streaming_manager.register_llm(info['provider'], llm)
                    ctx.console.print(f"[dim]Streaming LLM registered for {info['provider']}[/]")
            except Exception as e:
                # Non-critical: streaming still works via dynamic registration
                ctx.console.print(f"[yellow]Warning: Could not pre-register streaming LLM: {e}[/]")
        
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
            # Clear agent manager cache to use new config
            # Note: cache clearing is now handled by factory registry
            try:
                from src.agents.langchain.factories.registry import get_global_registry
                registry = get_global_registry()
                registry.clear_cache()
            except Exception as cache_error:
                # Non-critical: just log the warning
                pass
            
            return {
                "type": "success",
                "message": "LLM configuration reloaded successfully",
                "payload": {
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