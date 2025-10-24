# Middleware Integration Verification

## Purpose
Verify that SubAgentMiddleware implementation doesn't conflict with the service layer and follows proper separation of concerns.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
│  src/application/commands/agent/deep/                       │
│  - mode_commands.py: /mode deep (switch agent mode)         │
│  - use_commands.py: /use <function> (switch function type)  │
│  - deep_commands.py: /deep <cmd> (query middleware status)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│  src/application/services/agent/deep/                       │
│  - agent_lifecycle.py: create_default_deep_agent()          │
│  - deep_agent_manager.py: DeepAgentManager                  │
│  - service.py: DeepAgentService.get_info()                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Factory Layer                          │
│  src/agents/deepagents/factories/base.py                    │
│  - DeepAgentFactory.create_agent()                          │
│  - _build_subagent_specs(): Create SubAgent specs           │
│                             with configured LLM instances   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      Runtime Layer                          │
│  src/components/deepagents/runtime.py                       │
│  - create_deep_agent_runtime()                              │
│    1. Create SubAgentMiddleware with SubAgent specs         │
│    2. Call get_task_tool() to get task tool                 │
│    3. Add task tool to tools list                           │
│    4. Call create_agent() with tools + middleware           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Middleware Layer                         │
│  src/components/deepagents/runtime_middlewares/__init__.py  │
│  - SubAgentMiddleware:                                      │
│    - __init__(): Store SubAgent specs                       │
│    - _create_subagent_runnables(): Create agent instances   │
│    - get_task_tool(): Return StructuredTool for delegation  │
│    - wrap_model_call(): Inject system prompt                │
└─────────────────────────────────────────────────────────────┘
```

## Separation of Concerns

### Service Layer Responsibilities
**Location**: `src/application/services/agent/deep/`

**Functions**:
1. **Main Agent Lifecycle Management**:
   - `create_default_deep_agent()`: Initialize main agent
   - `switch_deep_agent()`: Switch between function types
   - `get_agent()`: Retrieve active agent instance

2. **Configuration Management**:
   - Load provider/model config from providers.json
   - Manage agent_instance in ctx.config["agent"]
   - Return agent metadata via `get_info()`

3. **High-Level Orchestration**:
   - Coordinate between commands and factory
   - No knowledge of middleware internals

**DOES NOT**:
- Create SubAgent runnables
- Provide task tools
- Manage SubAgent delegation logic

---

### Middleware Layer Responsibilities
**Location**: `src/components/deepagents/runtime_middlewares/`

**Functions**:
1. **SubAgent Runnable Creation**:
   - Take SubAgent specs from factory
   - Create runnable instances using `create_agent()`
   - Store in `_subagent_runnables` dict

2. **Task Tool Provision**:
   - Expose `get_task_tool()` method
   - Return StructuredTool that delegates to subagents
   - Define TaskInput schema with subagent_type parameter

3. **System Prompt Injection**:
   - Advertise available subagents via `wrap_model_call()`
   - Encourage deliberate delegation

**DOES NOT**:
- Manage main agent lifecycle
- Load configuration files
- Handle /mode or /use commands

---

## Integration Flow

### 1. User Runs `/mode deep`

**File**: `src/application/commands/agent/mode_commands.py:58-78`

```python
# Set provider/model configuration
config["provider"] = "ZHIPU"
config["model"] = "glm-4.6"
config["function_type"] = "research"

# Create agent immediately
agent, info = await create_default_deep_agent(ctx, target="deep")
config["agent_instance"] = agent
```

**Service Layer Called**: ✅ `create_default_deep_agent()`

---

### 2. Service Calls Factory

**File**: `src/application/services/agent/deep/agent_lifecycle.py:27-48`

```python
async def create_default_deep_agent(ctx, target: str = "deep"):
    config = ctx.get_engine_config("agent")
    function_type = config.get("function_type", "research")
    provider = config.get("provider", "ZHIPU")
    model = config.get("model", "glm-4.6")

    # Call factory to create agent
    agent = await deep_agent_manager.create_agent(
        ctx=ctx,
        function_type=function_type,
        provider=provider,
        model=model,
        target=target,
    )

    return agent, {...}  # Return agent + metadata
```

**Factory Called**: ✅ `deep_agent_manager.create_agent()`

---

### 3. Factory Builds SubAgent Specs

**File**: `src/agents/deepagents/factories/base.py:140-194`

```python
def _build_subagent_specs(self, function_type: str, tools: list) -> list[SubAgent]:
    subagent_types = subagent_manager.get_available_subagents()
    subagent_specs = []

    for subagent_type, config in subagent_types.items():
        # Get prompt, tools, model config
        prompt = prompt_registry.get_subagent_prompt(function_type, subagent_type)

        # Create LLM instance with base_url and api_key
        model_settings = {...}
        if "base_url" in config:
            model_settings["base_url"] = config["base_url"]
        if "api_key_env" in config:
            api_key = os.getenv(config["api_key_env"])
            if api_key:
                model_settings["api_key"] = api_key

        subagent_llm = init_chat_model(model_identifier, **model_settings)

        # Create SubAgent spec (NOT runnable yet)
        subagent_spec = SubAgent(
            name=subagent_type,
            description=description,
            system_prompt=prompt,
            tools=tools,
            model=subagent_llm,  # Pass LLM instance
            metadata={...},
        )
        subagent_specs.append(subagent_spec)

    return subagent_specs
```

**Result**: List of `SubAgent` dataclass instances with configured LLMs

**Note**: Factory creates SubAgent **SPECS**, not runnable instances. This is intentional - the specs contain all configuration needed for middleware to create runnables.

---

### 4. Factory Calls Runtime

**File**: `src/agents/deepagents/factories/base.py:100-125`

```python
async def create_agent(self, function_type: str, provider: str, model: str, ...):
    # Build middleware config
    middleware_config = deepagents_provider_registry.get_middleware_config()

    # Build SubAgent specs with configured LLMs
    subagent_specs = self._build_subagent_specs(function_type, tools)

    # Call runtime to create agent graph
    agent_graph = create_deep_agent_runtime(
        model=llm,
        system_prompt=system_prompt,
        tools=tools,
        middleware_config=middleware_config,
        subagents=subagent_specs,  # Pass specs to runtime
        ...
    )

    return DeepAgent(runnable=agent_graph, ...)
```

**Runtime Called**: ✅ `create_deep_agent_runtime()`

---

### 5. Runtime Creates SubAgentMiddleware

**File**: `src/components/deepagents/runtime.py:75-89`

```python
# Create SubAgentMiddleware with specs
subagent_middleware = SubAgentMiddleware(
    default_model=model,
    default_tools=tools or [],
    subagents=subagents or [],  # SubAgent specs from factory
    default_middleware=default_subagent_middleware,
    default_interrupt_on=interrupt_on,
    general_purpose_agent=True,
    task_description=subagents_cfg.get("task_description"),
)

# Get task tool from middleware
task_tool = subagent_middleware.get_task_tool()
if task_tool:
    tools = list(tools) if tools else []
    tools.append(task_tool)  # Add task tool to tools list
```

**Middleware Initialized**: ✅ SubAgentMiddleware creates runnable instances in `__init__`

---

### 6. SubAgentMiddleware Creates Runnables

**File**: `src/components/deepagents/runtime_middlewares/__init__.py:205-226`

```python
def _create_subagent_runnables(self) -> None:
    """Create runnable instances for each subagent using langchain.agents.create_agent."""
    from langchain.agents import create_agent

    for subagent_spec in self.subagents:
        if isinstance(subagent_spec, CompiledSubAgent):
            # Already compiled
            self._subagent_runnables[subagent_spec.name] = subagent_spec.runnable
        else:
            # Create agent from SubAgent spec
            subagent_model = subagent_spec.model if subagent_spec.model else self.default_model
            subagent_tools = list(subagent_spec.tools) if subagent_spec.tools else list(self.default_tools)

            # Create the subagent runnable
            subagent_runnable = create_agent(
                subagent_model,  # Use LLM instance from spec
                system_prompt=subagent_spec.system_prompt,
                tools=subagent_tools,
                middleware=self.default_middleware,
                checkpointer=False,
            )
            self._subagent_runnables[subagent_spec.name] = subagent_runnable
```

**Result**: `_subagent_runnables` dict populated with runnable instances

---

### 7. SubAgentMiddleware Provides Task Tool

**File**: `src/components/deepagents/runtime_middlewares/__init__.py:228-268`

```python
def get_task_tool(self) -> Any | None:
    """Create and return the task tool for subagent delegation."""
    if not self._subagent_runnables:
        return None

    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class TaskInput(BaseModel):
        subagent_type: str = Field(description=f"Type of subagent to use. Options: {', '.join(self._subagent_runnables.keys())}")
        description: str = Field(description="Detailed task description for the subagent")

    async def invoke_task(subagent_type: str, description: str) -> str:
        """Invoke a subagent to handle a specific task."""
        if subagent_type not in self._subagent_runnables:
            return f"Error: Unknown subagent type '{subagent_type}'. Available: {list(self._subagent_runnables.keys())}"

        subagent = self._subagent_runnables[subagent_type]
        try:
            result = await subagent.ainvoke({"messages": [{"role": "user", "content": description}]})
            messages = result.get("messages", [])
            if messages:
                return messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
            return "SubAgent completed but returned no response."
        except Exception as exc:
            return f"SubAgent execution failed: {exc}"

    task_tool = StructuredTool(
        name="task",
        description=f"Delegate complex tasks to specialized subagents. Available types: {', '.join(self._subagent_runnables.keys())}",
        func=lambda **kwargs: None,  # Sync not supported
        coroutine=invoke_task,
        args_schema=TaskInput,
    )

    return task_tool
```

**Result**: Returns StructuredTool that delegates to subagent runnables

---

### 8. Runtime Adds Task Tool and Creates Agent

**File**: `src/components/deepagents/runtime.py:85-114`

```python
# Get task tool from SubAgentMiddleware
task_tool = subagent_middleware.get_task_tool()
if task_tool:
    tools = list(tools) if tools else []
    tools.append(task_tool)  # Add to tools list

deepagent_middleware: List[AgentMiddleware] = [
    TodoListMiddleware(),
    filesystem_middleware,
    subagent_middleware,  # Inject system prompt about subagents
    SummarizationMiddleware(...),
    AnthropicPromptCachingMiddleware(...),
    PatchToolCallsMiddleware(),
]

# Create main agent with task tool + middleware
agent_graph = create_agent(
    model,
    system_prompt=system_prompt,
    tools=tools,  # Includes task tool
    middleware=deepagent_middleware,  # Includes SubAgentMiddleware
    checkpointer=checkpointer,
    store=store,
    cache=cache,
    debug=debug,
    name=name,
)
```

**Result**: Main agent created with:
- Task tool for delegation
- SubAgentMiddleware for system prompt injection
- Other middleware for filesystem, summarization, etc.

---

## Verification Checklist

### ✅ No Conflicts Between Layers

- [x] Service layer only manages main agent lifecycle
- [x] Service layer does NOT create SubAgent runnables
- [x] Service layer does NOT provide task tools
- [x] Middleware only handles SubAgent delegation
- [x] Middleware does NOT manage main agent configuration
- [x] Middleware does NOT handle /mode or /use commands

### ✅ Proper Data Flow

- [x] Factory creates SubAgent specs with configured LLMs
- [x] Runtime receives SubAgent specs and passes to middleware
- [x] Middleware creates runnable instances from specs
- [x] Middleware provides task tool via get_task_tool()
- [x] Runtime adds task tool to tools list before creating agent

### ✅ Correct LLM Configuration

- [x] Main agent uses providers.json configuration
- [x] SubAgents use subagents.json configuration
- [x] Each SubAgent LLM instance has correct base_url
- [x] Each SubAgent LLM instance has correct api_key
- [x] API keys extracted from environment using api_key_env

### ✅ Tool Integration

- [x] Task tool created in middleware layer
- [x] Task tool added to tools list in runtime layer
- [x] Task tool delegates to correct subagent runnable
- [x] Task tool handles errors gracefully

### ✅ System Prompt Injection

- [x] SubAgentMiddleware injects prompt via wrap_model_call()
- [x] System prompt advertises available subagents
- [x] System prompt encourages deliberate delegation

---

## Conclusion

**No conflicts detected** between service layer and middleware layer.

**Separation of concerns maintained**:
- Service layer: Main agent lifecycle
- Factory layer: SubAgent spec preparation
- Runtime layer: Agent graph assembly
- Middleware layer: SubAgent delegation

**Complete delegation workflow**:
1. User runs `/mode deep`
2. Service creates main agent via factory
3. Factory builds SubAgent specs with configured LLMs
4. Runtime creates SubAgentMiddleware with specs
5. Middleware creates subagent runnables in __init__
6. Middleware provides task tool via get_task_tool()
7. Runtime adds task tool to tools list
8. Main agent can invoke task tool to delegate work

**All fixes verified and documented in problem2-fixes.md**
