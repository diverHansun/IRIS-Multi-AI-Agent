# DeepAgents Services

## Overview

DeepAgents service layer provides comprehensive management for multi-agent operations, middleware coordination, and subagent lifecycle. The service architecture follows the same patterns as BasicAgents while adding advanced multi-agent capabilities.

## Service Architecture

### Directory Structure
```
src/application/services/agent/deep/
├── __init__.py
├── service.py              # Main DeepAgentService
├── agent_lifecycle.py      # Deep agent lifecycle management
├── conversation.py         # Multi-agent conversation handling
└── middleware/
    ├── __init__.py
    ├── filesystem_service.py    # Filesystem middleware service
    ├── subagents_service.py     # Subagents middleware service
    └── patch_tool_calls_service.py  # Patch tool calls service
```

## Core Services

### Streaming Considerations
DeepAgents do not use streaming output for the following reasons:
- **Middleware Requirements**: FilesystemMiddleware, SubAgentMiddleware need complete responses
- **Tool Calling**: Agent tool calls require complete message context
- **Subagent Communication**: Subagent coordination needs full message history
- **State Management**: Agent state transitions require complete execution results

LLM streaming is handled separately in `/mode llm` and is not applicable to agent operations.

### DeepAgentService
Main service coordinating deep agent operations with middleware support.

**Key Features:**
- Multi-agent coordination and management
- Middleware integration and lifecycle
- Subagent creation and communication
- Configuration management and validation

**Implementation:**
```python
# src/application/services/agent/deep/service.py
class DeepAgentService(BaseEngineService):
    """
    Service coordinating multi-agent operations for the deep mode.
    """
    
    @staticmethod
    def _config(ctx) -> Dict[str, Any]:
        return ctx.get_engine_config("agent")
    
    @staticmethod
    def _available_providers() -> List[str]:
        from src.core.providers import deepagents_provider_registry
        return deepagents_provider_registry.get_available_providers()
    
    async def initialize(self, ctx) -> Dict[str, Any]:
        """Initialize deep agent service with middleware support"""
        providers = self._available_providers()
        if not providers:
            return {
                "type": "error",
                "message": "No deep agent providers available. Please configure API keys.",
                "payload": {"providers": providers},
            }
        
        config = self._config(ctx)
        config["agent_type"] = "deep"
        
        # Create deep agent with middleware
        agent = await self._create_deep_agent(ctx, config)
        config["agent_instance"] = agent
        
        return {
            "type": "success",
            "message": "Deep agent engine initialized with middleware support",
            "payload": {
                "agent": agent.get_info(),
                "mode": {
                    "mode": "agent",
                    "agent_type": "deep",
                    "middleware": ["filesystem", "subagents", "patch_tool_calls"],
                    "streaming": False,  # DeepAgents do not use streaming
                    "session_id": ctx.session_id,
                },
            },
        }
    
    async def handle_query(self, ctx, query: str) -> str:
        """Handle multi-agent query with middleware support (no streaming)"""
        return await handle_deep_agent_query(ctx, query)
    
    async def _create_deep_agent(self, ctx, config: Dict[str, Any]) -> Any:
        """Create deep agent with middleware configuration"""
        from src.agents.deepagents.managers import deep_agent_manager
        
        # Get middleware configuration
        middleware_config = self._get_middleware_config()
        
        # Create deep agent
        agent = await deep_agent_manager.create_deep_agent(
            provider=config.get("provider"),
            model=config.get("model"),
            middleware_config=middleware_config,
            global_memory_manager=ctx.global_memory
        )
        
        return agent
```

### Agent Lifecycle Service
Manages deep agent creation, switching, and lifecycle operations.

**Implementation:**
```python
# src/application/services/agent/deep/agent_lifecycle.py
async def create_default_deep_agent(ctx, target: str = "deep") -> Tuple[Any, Dict[str, Any]]:
    """Create the default deep agent for the supplied target mode"""
    config = _agent_config(ctx)
    provider = config.get("provider")
    model = config.get("model")
    
    if not provider:
        # Use first available provider
        from src.core.providers import deepagents_provider_registry
        providers = deepagents_provider_registry.get_available_providers()
        provider = providers[0] if providers else "anthropic"
    
    agent = await _instantiate_deep_agent(ctx, provider, model)
    info = _update_config(config, provider, model, agent)
    
    return agent, info

async def _instantiate_deep_agent(ctx, provider: str, model: str | None) -> Any:
    """Instantiate deep agent with middleware support"""
    from src.agents.deepagents.managers import deep_agent_manager
    
    agent = await deep_agent_manager.create_deep_agent(
        provider=provider,
        model=model,
        global_memory_manager=ctx.global_memory,
    )
    
    return agent
```

### Conversation Service
Handles multi-agent conversations with middleware integration.

**Implementation:**
```python
# src/application/services/agent/deep/conversation.py
async def handle_deep_agent_query(ctx, query: str) -> str:
    """Handle deep agent query with middleware support (no streaming)"""
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")
    
    if agent is None:
        raise RuntimeError("Deep agent engine is not initialized.")
    
    # DeepAgents do not use streaming - wait for complete response
    with ctx.console.status("[dim]Deep agent reasoning with middleware...[/]"):
        result = await agent.ainvoke(query, session_id=ctx.session_id)
    
    if result.get("success"):
        answer = result.get("output", "No response generated.")
        ctx.console.print(f"[bold blue]Deep Agent >[/] {answer}")
        
        # Show middleware usage
        middleware_usage = result.get("middleware_usage", {})
        if middleware_usage:
            ctx.console.print(f"[dim]Middleware used: {', '.join(middleware_usage.keys())}[/]")
        
        # Show subagent usage
        subagent_calls = result.get("subagent_calls", 0)
        if subagent_calls:
            ctx.console.print(f"[dim]Subagents called: {subagent_calls}[/]")
        
        return answer
    
    error_message = result.get("error", "Unknown error")
    ctx.console.print(f"[bold red]Deep Agent Error: {error_message}[/]")
    return ""
```

## Middleware Services

### Filesystem Middleware Service
Manages filesystem operations with permission controls.

**Implementation:**
```python
# src/application/services/agent/deep/middleware/filesystem_service.py
class FilesystemMiddlewareService:
    """Service for managing filesystem middleware operations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.permission_mode = config.get("permission_mode", "read_only")
        self.security = config.get("security", {})
    
    def get_available_tools(self) -> List[str]:
        """Get available filesystem tools based on permission mode"""
        if self.permission_mode == "read_only":
            return ["read_file", "list_files", "search_files"]
        elif self.permission_mode == "ask_before_edit":
            return ["read_file", "list_files", "search_files", "write_file", "edit_file", "delete_file"]
        elif self.permission_mode == "edit_automatically":
            return ["read_file", "list_files", "search_files", "write_file", "edit_file", "delete_file"]
        return []
    
    def validate_operation(self, operation: str, path: str) -> bool:
        """Validate if operation is allowed for given path"""
        if operation in ["write_file", "edit_file", "delete_file"]:
            if self.permission_mode == "read_only":
                return False
            elif self.permission_mode == "ask_before_edit":
                return self._request_user_confirmation(operation, path)
        
        return True
```

### Subagents Middleware Service
Manages subagent creation, communication, and lifecycle.

**Implementation:**
```python
# src/application/services/agent/deep/middleware/subagents_service.py
class SubagentsMiddlewareService:
    """Service for managing subagent middleware operations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.available_subagents = config.get("subagents", {})
        self.max_concurrent = config.get("max_concurrent", 3)
        self.active_subagents = {}
    
    def get_available_subagents(self) -> Dict[str, Dict[str, Any]]:
        """Get available subagent types and configurations"""
        return self.available_subagents
    
    def create_subagent(self, subagent_type: str, task_description: str) -> str:
        """Create and execute subagent for specific task"""
        if subagent_type not in self.available_subagents:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
        
        if len(self.active_subagents) >= self.max_concurrent:
            raise RuntimeError(f"Maximum concurrent subagents reached: {self.max_concurrent}")
        
        # Create subagent instance
        subagent_config = self.available_subagents[subagent_type]
        subagent_id = f"{subagent_type}_{len(self.active_subagents)}"
        
        # Execute subagent task
        result = self._execute_subagent_task(subagent_config, task_description)
        
        # Clean up
        if subagent_id in self.active_subagents:
            del self.active_subagents[subagent_id]
        
        return result
    
    def get_subagent_status(self) -> Dict[str, Any]:
        """Get current subagent status"""
        return {
            "active_count": len(self.active_subagents),
            "max_concurrent": self.max_concurrent,
            "available_types": list(self.available_subagents.keys()),
            "active_subagents": list(self.active_subagents.keys())
        }
```

### Patch Tool Calls Service
Manages tool call patching and error recovery.

**Implementation:**
```python
# src/application/services/agent/deep/middleware/patch_tool_calls_service.py
class PatchToolCallsService:
    """Service for managing tool call patching operations"""
    
    def __init__(self):
        self.patched_calls = 0
        self.error_recovery_count = 0
    
    def patch_dangling_calls(self, messages: List[Any]) -> List[Any]:
        """Patch dangling tool calls in message history"""
        patched_messages = []
        
        for i, msg in enumerate(messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if not self._has_corresponding_tool_message(messages[i:], tool_call):
                        patched_messages.append(self._create_tool_cancellation_message(tool_call))
                        self.patched_calls += 1
        
        return patched_messages
    
    def get_patch_statistics(self) -> Dict[str, int]:
        """Get tool call patching statistics"""
        return {
            "patched_calls": self.patched_calls,
            "error_recovery_count": self.error_recovery_count
        }
```

## Configuration Integration

### Provider Registry Integration
```python
# src/core/providers/deepagents_provider_registry.py
class DeepAgentsProviderRegistry:
    """Provider registry for DeepAgents configurations"""
    
    def __init__(self, config_path: str = "config/agents/deep/models/providers.json"):
        self.config_path = config_path
        self._providers = {}
        self._middleware_config = {}
        self._load_from_config()
    
    def get_deep_agent_config(self, provider: str, model: str) -> Dict[str, Any]:
        """Get complete deep agent configuration"""
        provider_config = self._providers.get(provider.upper())
        if not provider_config:
            raise ValueError(f"Provider {provider} not found")
        
        model_config = provider_config.get("models", {}).get(model)
        if not model_config:
            raise ValueError(f"Model {model} not found in provider {provider}")
        
        return {
            "base_url": provider_config["base_url"],
            "api_key_env": provider_config["api_key_env"],
            "middleware": model_config.get("middleware", {}),
            "temperature": model_config.get("temperature", 0.6),
            "max_tokens": model_config.get("max_tokens", 4096)
        }
    
    def get_middleware_config(self) -> Dict[str, Any]:
        """Get middleware configuration"""
        return self._middleware_config
```

## Service Integration

### Service Registration
```python
# src/application/services/__init__.py
def get_current_service(ctx) -> BaseEngineService:
    """Get current service based on engine mode"""
    mode = ctx.get_engine_mode()
    
    if mode == "agent":
        agent_type = ctx.get_engine_config("agent").get("agent_type", "basic")
        if agent_type == "deep":
            from src.application.services.agent.deep.service import DeepAgentService
            return DeepAgentService()
        else:
            from src.application.services.agent.basic.service import BasicAgentService
            return BasicAgentService()
    
    # ... other service routing
```

### Middleware Service Integration
```python
# src/application/services/agent/deep/middleware/__init__.py
from .filesystem_service import FilesystemMiddlewareService
from .subagents_service import SubagentsMiddlewareService
from .patch_tool_calls_service import PatchToolCallsService

__all__ = [
    "FilesystemMiddlewareService",
    "SubagentsMiddlewareService", 
    "PatchToolCallsService"
]
```

## Error Handling

### Service Error Recovery
```python
class DeepAgentServiceError(Exception):
    """Base exception for deep agent service errors"""
    pass

class MiddlewareError(DeepAgentServiceError):
    """Middleware-specific errors"""
    pass

class SubagentError(DeepAgentServiceError):
    """Subagent-specific errors"""
    pass

def handle_deep_agent_error(error: Exception) -> Dict[str, Any]:
    """Handle deep agent service errors"""
    if isinstance(error, MiddlewareError):
        return {
            "type": "error",
            "message": f"Middleware error: {error}",
            "payload": {"error_type": "middleware"}
        }
    elif isinstance(error, SubagentError):
        return {
            "type": "error", 
            "message": f"Subagent error: {error}",
            "payload": {"error_type": "subagent"}
        }
    else:
        return {
            "type": "error",
            "message": f"Deep agent error: {error}",
            "payload": {"error_type": "general"}
        }
```

## Performance Considerations

### Service Optimization
- **Middleware Caching**: Cache middleware configurations for performance
- **Subagent Pooling**: Pool subagent instances for reuse
- **Resource Management**: Monitor and limit resource usage
- **Error Recovery**: Implement robust error recovery mechanisms

### Monitoring and Metrics
- **Service Metrics**: Track service performance and usage
- **Middleware Metrics**: Monitor middleware operation statistics
- **Subagent Metrics**: Track subagent creation and execution
- **Error Metrics**: Monitor error rates and recovery success
