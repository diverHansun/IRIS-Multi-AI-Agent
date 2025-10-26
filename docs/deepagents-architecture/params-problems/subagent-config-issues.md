# SubAgent Configuration Parameter Flow Issues

## Document Information
- **Date**: 2025-10-26
- **Version**: 1.0
- **Status**: Analysis Complete, Fixes Pending

## Executive Summary

The SubAgent configuration system has three critical issues preventing configuration parameters from flowing correctly from JSON files to runtime execution. While the configuration extraction layer (Registry) works correctly, parameters are lost during the Factory and Middleware stages due to incomplete data structures, missing parameter passing, and hardcoded logic.

## Problem 1: Incomplete Data Structure Design

### Root Cause
The `SubAgent` dataclass does not include fields for all configuration parameters defined in the JSON configuration file.

### Location
`src/components/deepagents/runtime_middlewares/__init__.py` - `SubAgent` dataclass

### Current State
```python
@dataclass(slots=True)
class SubAgent:
    name: str
    description: str
    system_prompt: str
    tools: Sequence[Any] = field(default_factory=list)
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recursion_limit: Optional[int] = None
    step_timeout: Optional[float] = None
    # Missing: middleware
    # Missing: checkpointer
    # Missing: display_config
```

### Impact
- Cannot store middleware configuration from JSON
- Cannot store checkpointer settings
- Cannot store display preferences
- Subsequent layers have no way to access these parameters

### Required Fields
Based on `config/agents/deep/models/subagents.json`:
- `middleware`: List of additional middleware components
- `checkpointer`: Checkpointer configuration
- `display_config`: Display and streaming preferences

## Problem 2: Factory Layer Parameter Passing Interruption

### Root Cause
The Factory layer reads complete configuration from Registry but only passes partial parameters to the SubAgent spec.

### Location
`src/agents/deepagents/factories/base.py` - `_build_subagent_specs()` method

### Current State
```python
# Configuration is retrieved completely
config = subagent_manager.get_subagent_config(subagent_type)
agent_config = config["agent_config"]      # Contains tools, middleware, checkpointer
display_config = config["display_config"]  # Contains streaming settings
metadata = config["metadata"]              # Contains context information

# But SubAgent spec creation ignores most parameters
subagent_spec = SubAgent(
    name=config["name"],
    description=description,
    system_prompt=system_prompt,
    tools=[],  # Hardcoded empty list, ignores agent_config["tools"]
    model=subagent_llm,
    recursion_limit=recursion_limit,
    step_timeout=max_execution_time,
    # agent_config["middleware"] not passed
    # agent_config["checkpointer"] not passed
    # display_config not passed
)
```

### Impact
- `agent_config.tools` configuration is read but never used
- `agent_config.middleware` configuration is completely ignored
- `agent_config.checkpointer` configuration is completely ignored
- `display_config` is only used for metadata recording, not runtime behavior

## Problem 3: Middleware Layer Hardcoded Logic

### Root Cause
The SubAgentMiddleware layer uses hardcoded values instead of respecting configuration from the SubAgent spec.

### Location
`src/components/deepagents/runtime_middlewares/__init__.py` - `_create_subagent_runnables()` method

### Current State
```python
# Tool logic error: tools is always [], so always uses default_tools
subagent_tools = list(subagent_spec.tools) if subagent_spec.tools else list(self.default_tools)

# Hardcoded middleware: always uses default, ignoring configuration
middleware=self.default_middleware,

# Hardcoded checkpointer: always False, ignoring configuration
checkpointer=False,
```

### Impact
- Custom tools for specific SubAgents are never used
- Custom middleware cannot be added to SubAgents
- SubAgent state persistence is always disabled
- No differentiation between SubAgent types at runtime

## Parameter Flow Analysis

### Complete Parameter Flow Chain

```
Stage 1: Configuration File
config/agents/deep/models/subagents.json
├── llm_config
├── agent_config (tools, middleware, checkpointer)
├── runtime_limits (recursion_limit, max_execution_time)
├── display_config (streaming_enabled, show_*)
└── metadata (context_window, supports_tools)
        ↓ [LOADED BY]
        
Stage 2: Registry Extraction [OK]
SubAgentsProviderRegistry.get_subagent_config()
├── _extract_llm_config() → llm_config ✓
├── _extract_agent_config() → agent_config ✓
├── _extract_runtime_limits() → runtime_limits ✓
├── _extract_display_config() → display_config ✓
└── _extract_metadata() → metadata ✓
        ↓ [PASSED TO]

Stage 3: Factory Building [BREAKS HERE]
BaseDeepAgentFactory._build_subagent_specs()
├── llm_config → Used for LLM creation ✓
├── runtime_limits → Passed to SubAgent spec ✓
├── agent_config → Read but NOT passed ✗
├── display_config → Used only for metadata ✗
└── metadata → Used only for metadata ✗
        ↓ [CREATES]

Stage 4: SubAgent Dataclass [INCOMPLETE]
SubAgent(
    tools=[],  ← Hardcoded, should be agent_config["tools"]
    recursion_limit=X,  ← Correct
    step_timeout=Y,  ← Correct
    # Missing: middleware field
    # Missing: checkpointer field
    # Missing: display_config field
)
        ↓ [USED BY]

Stage 5: Middleware Creation [HARDCODED]
SubAgentMiddleware._create_subagent_runnables()
├── tools → Always uses default_tools ✗
├── middleware → Always uses default_middleware ✗
└── checkpointer → Always False ✗
```

### Parameter Usage Status Table

| Configuration Section | Parameter | Registry Extract | Pass to SubAgent | Runtime Use | Status |
|-----------------------|-----------|------------------|------------------|-------------|---------|
| llm_config | provider | Yes | Yes | Yes | OK |
| llm_config | model | Yes | Yes | Yes | OK |
| llm_config | model_params | Yes | Yes | Yes | OK |
| agent_config | tools | Yes | **No** | **No** | **BROKEN** |
| agent_config | middleware | Yes | **No** | **No** | **BROKEN** |
| agent_config | checkpointer | Yes | **No** | **No** | **BROKEN** |
| runtime_limits | recursion_limit | Yes | Yes | Yes | OK |
| runtime_limits | max_execution_time | Yes | Yes | Yes | OK |
| display_config | streaming_enabled | Yes | **No** | Metadata only | **PARTIAL** |
| display_config | show_reasoning_steps | Yes | **No** | **No** | **BROKEN** |
| display_config | show_tool_calls | Yes | **No** | **No** | **BROKEN** |
| metadata | context_window | Yes | **No** | Metadata only | **PARTIAL** |
| metadata | supports_tools | Yes | **No** | Metadata only | **PARTIAL** |

## Impact Scope

### Affected Components
1. **SubAgent Runtime Behavior**: Cannot customize tools, middleware, or checkpointer per SubAgent type
2. **Configuration System**: 40% of configuration parameters are unused
3. **SubAgent Differentiation**: All SubAgents behave identically regardless of configuration
4. **Performance**: Cannot optimize specific SubAgents (e.g., disable features for simple tasks)

### User-Visible Effects
1. Cannot assign specialized tools to specific SubAgents (e.g., search tools only for research SubAgent)
2. Cannot enable state persistence for long-running SubAgent tasks
3. Cannot customize display behavior per SubAgent
4. SubAgent configuration changes have no effect on runtime behavior

## Fix Strategy

### Phase 1: Data Structure Extension

**File**: `src/components/deepagents/runtime_middlewares/__init__.py`

Add missing fields to `SubAgent` dataclass:
```python
@dataclass(slots=True)
class SubAgent:
    name: str
    description: str
    system_prompt: str
    tools: Sequence[Any] = field(default_factory=list)
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recursion_limit: Optional[int] = None
    step_timeout: Optional[float] = None
    # Add these fields
    middleware: Sequence[Any] = field(default_factory=list)
    checkpointer: Optional[Any] = None
    display_config: Dict[str, Any] = field(default_factory=dict)
```

### Phase 2: Factory Parameter Passing

**File**: `src/agents/deepagents/factories/base.py`

Pass all configuration parameters to SubAgent spec:
```python
agent_config = config["agent_config"]
display_config = config["display_config"]
metadata_cfg = config["metadata"]

subagent_spec = SubAgent(
    name=config["name"],
    description=description,
    system_prompt=system_prompt,
    tools=agent_config.get("tools", []),  # Use configured tools
    model=subagent_llm,
    recursion_limit=recursion_limit,
    step_timeout=max_execution_time,
    middleware=agent_config.get("middleware", []),  # Pass middleware
    checkpointer=agent_config.get("checkpointer", False),  # Pass checkpointer
    display_config=display_config,  # Pass display config
    metadata=metadata_cfg,  # Pass metadata
)
```

### Phase 3: Middleware Logic Correction

**File**: `src/components/deepagents/runtime_middlewares/__init__.py`

Use configuration instead of hardcoded values:
```python
# Merge custom tools with defaults
custom_tools = list(subagent_spec.tools) if subagent_spec.tools else []
combined_tools = [*custom_tools, *self.default_tools] if custom_tools else list(self.default_tools)

# Merge custom middleware with defaults
custom_middleware = list(subagent_spec.middleware) if subagent_spec.middleware else []
combined_middleware = [*self.default_middleware, *custom_middleware]

# Use configured checkpointer
checkpointer = subagent_spec.checkpointer if hasattr(subagent_spec, 'checkpointer') else False

subagent_runnable = create_agent(
    subagent_model,
    system_prompt=subagent_spec.system_prompt,
    tools=combined_tools,  # Use merged tools
    middleware=combined_middleware,  # Use merged middleware
    checkpointer=checkpointer,  # Use configured checkpointer
)
```

## Implementation Priority

### P0 (Critical - Must Fix)
1. Extend `SubAgent` dataclass with missing fields
2. Pass `agent_config` parameters from Factory to SubAgent spec
3. Correct hardcoded logic in Middleware layer

### P1 (High - Should Fix)
4. Add validation to ensure configuration parameters are used
5. Add logging for configuration parameter flow
6. Update tests to verify parameter passing

### P2 (Medium - Nice to Have)
7. Refactor merging strategy for tools and middleware
8. Document configuration parameter semantics
9. Add configuration validation at load time

## Testing Strategy

### Unit Tests Required
1. Test `SubAgent` dataclass can store all configuration parameters
2. Test Factory passes all parameters to SubAgent spec
3. Test Middleware uses configuration instead of defaults
4. Test custom tools are properly merged with defaults
5. Test custom middleware is properly applied

### Integration Tests Required
1. Test SubAgent with custom tools configuration
2. Test SubAgent with custom middleware configuration
3. Test SubAgent with checkpointer enabled
4. Test display_config affects runtime behavior

## References

- Configuration File: `config/agents/deep/models/subagents.json`
- Registry Implementation: `src/core/providers/subagents_provider_registry.py`
- Factory Implementation: `src/agents/deepagents/factories/base.py`
- Middleware Implementation: `src/components/deepagents/runtime_middlewares/__init__.py`

## Change History

- 2025-10-26: Initial analysis and documentation


