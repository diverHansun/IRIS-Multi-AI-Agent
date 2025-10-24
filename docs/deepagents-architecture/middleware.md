# DeepAgents Middleware

## Overview

Middleware provides core functionality for DeepAgents through interceptors that enhance agent capabilities without modifying core agent logic. The middleware system includes filesystem operations, subagent management, and advanced memory features.

## Architecture

### Middleware Location
```
src/application/services/shared/middleware/
├── __init__.py
├── filesystem.py      # File system operations and memory
├── subagents.py      # Subagent management and communication
├── memory.py         # Advanced memory management
└── registry.py       # Middleware registration and discovery
```

### Core Components

#### PatchToolCallsMiddleware
Handles dangling tool calls in message history to ensure proper tool execution flow.

**Key Features:**
- Detects and patches dangling tool calls
- Prevents tool execution failures
- Maintains message history integrity
- Automatic error recovery

**Implementation:**
```python
class PatchToolCallsMiddleware(AgentMiddleware):
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        """Before agent runs, handle dangling tool calls"""
        messages = state["messages"]
        patched_messages = []
        
        for i, msg in enumerate(messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if not self._has_corresponding_tool_message(messages[i:], tool_call):
                        patched_messages.append(self._create_tool_cancellation_message(tool_call))
        
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched_messages]}
```

#### FilesystemMiddleware
Provides secure file system operations with configurable access controls.

**Key Features:**
- File reading with path validation
- Configurable access modes (read-only, ask-before-edit, auto-edit)
- Security controls (allowed paths, file size limits)
- Long-term memory integration

**Implementation:**
```python
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.allowed_paths = config.get("allowed_paths", [])
        self.mode = config.get("mode", "read_only")
        self.tools = self._create_filesystem_tools()
    
    def _create_filesystem_tools(self):
        tools = [self._create_read_file_tool()]
        
        if self.mode in ["ask_before_edits", "edit_automatically"]:
            tools.extend([
                self._create_write_file_tool(),
                self._create_edit_file_tool()
            ])
        
        return tools
```

#### SubAgentMiddleware
Manages subagent lifecycle and communication.

**Key Features:**
- Subagent creation and management
- Task delegation and result collection
- Resource isolation and context management
- Communication protocols

**Implementation:**
```python
class SubAgentMiddleware(AgentMiddleware):
    def __init__(self, subagent_manager: SubAgentManager):
        self.subagent_manager = subagent_manager
        self.task_tool = self._create_task_tool()
    
    def _create_task_tool(self):
        return StructuredTool.from_function(
            func=self._execute_task,
            name="task",
            description="Launch subagent for complex tasks"
        )
```

## Configuration

### Filesystem Configuration
```json
{
  "enabled": true,
  "mode": "read_only",
  "security": {
    "allowed_paths": ["/workspace/", "/data/", "/tmp/"],
    "excluded_paths": ["/etc/", "/root/", "/home/"],
    "max_file_size": 10485760,
    "excluded_extensions": [".exe", ".bat", ".sh"]
  }
}
```

### Subagent Configuration
```json
{
  "enabled": true,
  "max_concurrent": 3,
  "timeout": 300,
  "subagents": {
    "research": {
      "provider": "zhipu",
      "model": "glm-4",
      "tools": ["internet_search", "file_read"]
    },
    "coding": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "tools": ["code_analysis", "file_edit"]
    }
  }
}
```

## Integration Points

### Tool System Integration
Middleware extends the existing tool system by providing new tools while maintaining compatibility with UnifiedToolManager.

```python
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, tool_manager: UnifiedToolManager):
        self.tool_manager = tool_manager
        self.filesystem_tools = self._create_filesystem_tools()
        
        # Register new tools with existing manager
        self.tool_manager.register_tools(self.filesystem_tools)
```

### Memory System Integration
Middleware extends memory capabilities by integrating with GlobalMemoryManager and adding filesystem-based long-term memory.

```python
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, memory_manager: GlobalMemoryManager):
        self.memory_manager = memory_manager
        self.filesystem_memory = FilesystemMemory(memory_manager)
        
        # Integrate with existing memory system
        self.long_term_memory = LongTermMemory(memory_manager)
```

### Configuration System Integration
Middleware configuration is managed through the existing configuration system with extensions for deep agent specific settings.

```python
class MiddlewareConfigLoader:
    def __init__(self, provider_registry: ProviderRegistry):
        self.provider_registry = provider_registry
    
    def load_middleware_config(self):
        # Load from config/agents/deep/middleware/
        filesystem_config = self._load_filesystem_config()
        subagents_config = self._load_subagents_config()
        
        return {
            "filesystem": filesystem_config,
            "subagents": subagents_config
        }
```

## Security Considerations

### Filesystem Security
- **Path Validation**: All file operations are restricted to configured allowed paths
- **Mode Enforcement**: Filesystem mode determines available operations
- **Size Limits**: File size restrictions prevent resource abuse
- **Extension Filtering**: Dangerous file types are excluded

### Subagent Security
- **Resource Isolation**: Subagents run in isolated contexts
- **Timeout Controls**: Subagent execution timeouts prevent resource exhaustion
- **Model Restrictions**: Subagent models are restricted to configured options
- **Communication Limits**: Subagent communication is limited to task results

## Error Handling

### Middleware Error Recovery
- **Graceful Degradation**: Failed middleware components are disabled without affecting core functionality
- **Error Propagation**: Middleware errors are properly propagated to the agent system
- **Logging**: All middleware operations are logged for debugging and security analysis

### Configuration Error Handling
- **Validation**: Configuration changes are validated before application
- **Fallback**: Invalid configurations fall back to safe defaults
- **Rollback**: Failed configuration changes are automatically rolled back

## Performance Considerations

### Resource Management
- **Memory Usage**: Middleware components are designed for efficient memory usage
- **Tool Caching**: Frequently used tools are cached for performance
- **Lazy Loading**: Middleware components are loaded only when needed

### Scalability
- **Concurrent Operations**: Middleware supports concurrent subagent operations
- **Resource Limits**: Configurable limits prevent resource exhaustion
- **Cleanup**: Proper cleanup of resources when middleware is disabled
