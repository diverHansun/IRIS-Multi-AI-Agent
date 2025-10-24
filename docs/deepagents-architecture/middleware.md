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
# src/application/services/shared/middleware/patch_tool_calls.py
class PatchToolCallsMiddleware(AgentMiddleware):
    """Middleware to patch dangling tool calls in the messages history."""
    
    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Before the agent runs, handle dangling tool calls from any AIMessage."""
        messages = state["messages"]
        if not messages or len(messages) == 0:
            return None
        
        patched_messages = []
        # Iterate over the messages and add any dangling tool calls
        for i, msg in enumerate(messages):
            patched_messages.append(msg)
            if msg.type == "ai" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    corresponding_tool_msg = next(
                        (msg for msg in messages[i:] if msg.type == "tool" and msg.tool_call_id == tool_call["id"]),
                        None,
                    )
                    if corresponding_tool_msg is None:
                        # We have a dangling tool call which needs a ToolMessage
                        tool_msg = (
                            f"Tool call {tool_call['name']} with id {tool_call['id']} was "
                            "cancelled - another message came in before it could be completed."
                        )
                        patched_messages.append(
                            ToolMessage(
                                content=tool_msg,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )
        
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *patched_messages]}
```

#### FilesystemMiddleware
Provides comprehensive file system operations with permission-based access controls, based on official deepagents implementation.

**Key Features:**
- Complete file system operations (read, write, edit, delete, search)
- Permission-based access control (read-only, ask-before-edit, auto-edit)
- Advanced security controls (path validation, file size limits, extension filtering)
- State management with file metadata tracking
- Long-term memory integration

**Permission Modes:**
```python
class FilesystemPermissionMode(Enum):
    READ_ONLY = "read_only"                    # Only read operations
    ASK_BEFORE_EDITS = "ask_before_edits"     # Edit operations require user confirmation
    EDIT_AUTOMATICALLY = "edit_automatically" # All operations allowed automatically
```

**Implementation:**
```python
class FilesystemMiddleware(AgentMiddleware):
    def __init__(self, 
                 permission_mode: str = "read_only",
                 allowed_paths: List[str] = None,
                 excluded_paths: List[str] = None,
                 max_file_size: int = 10485760,
                 excluded_extensions: List[str] = None,
                 long_term_memory: bool = False):
        self.permission_mode = permission_mode
        self.allowed_paths = allowed_paths or ["/workspace/", "/data/", "/tmp/"]
        self.excluded_paths = excluded_paths or ["/etc/", "/root/", "/home/"]
        self.max_file_size = max_file_size
        self.excluded_extensions = excluded_extensions or [".exe", ".bat", ".sh"]
        self.long_term_memory = long_term_memory
        
        # Create tools based on permission mode
        self.tools = self._create_tools_based_on_permission()
    
    def _create_tools_based_on_permission(self):
        """Create tools based on permission mode"""
        tools = [
            self._create_read_file_tool(),
            self._create_list_files_tool(),
            self._create_search_files_tool()
        ]
        
        if self.permission_mode in ["ask_before_edits", "edit_automatically"]:
            tools.extend([
                self._create_write_file_tool(),
                self._create_edit_file_tool(),
                self._create_delete_file_tool()
            ])
        
        return tools
    
    def _validate_path(self, path: str) -> str:
        """Validate and normalize file path for security"""
        # Prevent directory traversal attacks
        if ".." in path or path.startswith("~"):
            raise ValueError(f"Path traversal not allowed: {path}")
        
        # Normalize path
        normalized = os.path.normpath(path).replace("\\", "/")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        
        # Check allowed paths
        if not any(normalized.startswith(allowed) for allowed in self.allowed_paths):
            raise ValueError(f"Path not in allowed directories: {path}")
        
        # Check excluded paths
        if any(normalized.startswith(excluded) for excluded in self.excluded_paths):
            raise ValueError(f"Path in excluded directories: {path}")
        
        return normalized
```

**File State Management:**
```python
class FileData(TypedDict):
    """Data structure for storing file contents with metadata"""
    content: list[str]           # Lines of the file
    created_at: str             # ISO 8601 timestamp of file creation
    modified_at: str            # ISO 8601 timestamp of last modification

def _file_data_reducer(left: dict[str, FileData] | None, 
                      right: dict[str, FileData | None]) -> dict[str, FileData]:
    """Merge file updates with support for deletions"""
    if left is None:
        return {k: v for k, v in right.items() if v is not None}
    
    result = {**left}
    for key, value in right.items():
        if value is None:
            result.pop(key, None)  # Deletion marker
        else:
            result[key] = value
    return result
```

#### SubAgentMiddleware
Manages subagent lifecycle and communication, based on official deepagents implementation.

**Key Features:**
- Subagent creation and management with isolated context
- Task delegation and result collection
- Resource isolation and context management
- Communication protocols with state exclusion
- Support for both custom and general-purpose subagents

**SubAgent Types:**
```python
class SubAgent(TypedDict):
    """Specification for a custom subagent"""
    name: str                    # The name of the agent
    description: str             # Description for task selection
    system_prompt: str          # System prompt for the agent
    tools: Sequence[BaseTool | Callable | dict[str, Any]]  # Tools available
    model: NotRequired[str | BaseChatModel]  # Model for the agent
    middleware: NotRequired[list[AgentMiddleware]]  # Additional middleware
    interrupt_on: NotRequired[dict[str, bool | InterruptOnConfig]]  # Tool configs

class CompiledSubAgent(TypedDict):
    """A pre-compiled agent spec"""
    name: str                   # The name of the agent
    description: str            # Description for task selection
    runnable: Runnable          # The Runnable to use for the agent
```

**Implementation:**
```python
class SubAgentMiddleware(AgentMiddleware):
    def __init__(self,
                 default_model: str | BaseChatModel,
                 default_tools: Sequence[BaseTool | Callable | dict[str, Any]] = None,
                 default_middleware: list[AgentMiddleware] = None,
                 default_interrupt_on: dict[str, bool | InterruptOnConfig] = None,
                 subagents: list[SubAgent | CompiledSubAgent] = None,
                 system_prompt: str = None,
                 general_purpose_agent: bool = True,
                 task_description: str = None):
        self.default_model = default_model
        self.default_tools = default_tools or []
        self.default_middleware = default_middleware or []
        self.default_interrupt_on = default_interrupt_on
        self.subagents = subagents or []
        self.system_prompt = system_prompt or TASK_SYSTEM_PROMPT
        self.general_purpose_agent = general_purpose_agent
        self.task_description = task_description
        
        # Create task tool
        self.task_tool = self._create_task_tool()
    
    def _create_task_tool(self):
        """Create the task tool for subagent invocation"""
        return StructuredTool.from_function(
            func=self._execute_task,
            name="task",
            description=self.task_description or TASK_TOOL_DESCRIPTION
        )
    
    def _execute_task(self, 
                     subagent_type: str,
                     task_description: str,
                     **kwargs) -> str:
        """Execute task using specified subagent"""
        # Find the appropriate subagent
        subagent = self._find_subagent(subagent_type)
        
        # Create agent with middleware
        agent = create_agent(
            model=subagent.get("model", self.default_model),
            tools=subagent.get("tools", self.default_tools),
            middleware=self.default_middleware + subagent.get("middleware", []),
            interrupt_on=subagent.get("interrupt_on", self.default_interrupt_on)
        )
        
        # Execute task with isolated context
        result = agent.invoke({
            "messages": [HumanMessage(content=task_description)]
        })
        
        return result["messages"][-1].content
```

**Task Tool Description:**
```python
TASK_TOOL_DESCRIPTION = """Launch an ephemeral subagent to handle complex, multi-step independent tasks with isolated context windows.

Available agent types and the tools they have access to:
{available_agents}

When using the Task tool, you must specify a subagent_type parameter to select which agent type to use.

## Usage notes:
1. Launch multiple agents concurrently whenever possible, to maximize performance
2. When the agent is done, it will return a single message back to you
3. Each agent invocation is stateless
4. The agent's outputs should generally be trusted
5. Clearly tell the agent whether you expect it to create content, perform analysis, or just do research
6. If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first
7. When only the general-purpose agent is provided, you should use it for all tasks
"""
```

**State Management:**
```python
# State keys that should be excluded when passing state to subagents
_EXCLUDED_STATE_KEYS = ("messages", "todos")

def _filter_state_for_subagent(state: dict) -> dict:
    """Filter state to exclude sensitive keys when passing to subagents"""
    return {k: v for k, v in state.items() if k not in _EXCLUDED_STATE_KEYS}
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
