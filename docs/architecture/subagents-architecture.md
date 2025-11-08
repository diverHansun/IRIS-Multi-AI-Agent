# SubAgents Architecture Documentation

## Overview

This document describes the architecture of the SubAgents system in the DeepAgents framework, including the configuration flow, component responsibilities, and recent optimizations.

## Architecture Components

The SubAgents system follows a clean, layered architecture that separates concerns according to SOLID principles:

```
Configuration Layer
    └─> [config/agents/deep/models/subagents.json]
         └─> Provider Layer
              └─> [SubAgentsProviderRegistry]
                   └─> Factory Layer
                        └─> [BaseDeepAgentFactory]
                             └─> Runtime Layer
                                  └─> [SubAgentMiddleware]
                                       └─> Execution
```

## 1. Configuration Source

**Location**: `config/agents/deep/models/subagents.json`

**Responsibilities**:
- Define available subagent types (research, coding, analysis)
- Specify LLM configuration for each subagent
- Configure runtime limits and display preferences
- Set agent-specific tools and middleware

**Structure**:
```json
{
  "research": {
    "name": "research",
    "description": "Research specialist for deep information gathering",
    "llm_config": {
      "provider": "zhipu",
      "model": "glm-4.5-flash",
      "api_config": { ... },
      "model_params": { ... }
    },
    "agent_config": {
      "tools": [],
      "middleware": [],
      "checkpointer": false
    },
    "runtime_limits": {
      "max_execution_time": 300,
      "recursion_limit": 80,
      "step_timeout": 180
    },
    "display_config": { ... },
    "metadata": { ... }
  }
}
```

## 2. Configuration Provider

**Location**: `src/core/providers/subagents_provider_registry.py`

**Class**: `SubAgentsProviderRegistry`

**Responsibilities**:
- Load and parse subagents.json configuration
- Categorize parameters into logical groups:
  - `llm_config`: Provider, model, API configuration
  - `agent_config`: Tools, middleware, checkpointer
  - `runtime_limits`: Execution constraints
  - `display_config`: Streaming and logging preferences
  - `metadata`: Informational data
- Integrate with prompt registry for system prompts
- Provide clean parameter extraction via `get_llm_params_only()`

**Key Methods**:
```python
def get_subagent_config(subagent_type: str) -> Dict[str, Any]:
    """Returns categorized configuration for a subagent type."""

def get_llm_params_only(subagent_type: str) -> Dict[str, Any]:
    """Returns only LLM API parameters (temperature, max_tokens, etc.)."""
```

**SOLID Principles Applied**:
- **SRP**: Only manages configuration, no business logic
- **OCP**: New subagent types added via JSON without code changes
- **DIP**: Depends on configuration files, not concrete implementations

## 3. Factory Pattern

**Location**: `src/agents/deepagents/factories/base.py`

**Class**: `BaseDeepAgentFactory`

**Responsibilities**:
- Build SubAgent specifications from configuration
- Create LLM instances using `init_chat_model`
- Assemble middleware stacks
- Construct metadata for tracking

**Key Method**: `_build_subagent_specs()`

**Process Flow**:
```python
1. Get available subagents from manager
2. For each subagent type:
   a. Load configuration from SubAgentsProviderRegistry
   b. Extract LLM parameters
   c. Create LLM instance with init_chat_model()
   d. Build SubAgent dataclass with all parameters
   e. Collect metadata for tracking
3. Return (subagent_specs, metadata)
```

**Parameter Categories Handled**:
- LLM configuration (provider, model, API keys)
- Runtime limits (recursion_limit, step_timeout, max_execution_time)
- Agent configuration (tools, middleware, checkpointer)
- Display preferences (streaming, logging)

## 4. Runtime Middleware

**Location**: `src/components/deepagents/runtime_middlewares/subagents/`

**New Modular Structure** (After Refactoring):
```
subagents/
├── __init__.py          # Clean exports
├── types.py             # SubAgent, CompiledSubAgent dataclasses
└── middleware.py        # SubAgentMiddleware implementation
```

### 4.1 Data Types (`types.py`)

**Classes**:
- `SubAgent`: Lightweight specification for a subagent
- `CompiledSubAgent`: Wrapper for pre-compiled subagent runnables

**SubAgent Fields**:
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
    max_execution_time: Optional[float] = None
    middleware: Sequence[Any] = field(default_factory=list)
    checkpointer: Optional[Any] = None
    display_config: Dict[str, Any] = field(default_factory=dict)
```

### 4.2 Middleware (`middleware.py`)

**Class**: `SubAgentMiddleware`

**Responsibilities**:
- Advertise available subagents to main agent
- Create task delegation tool
- Manage subagent lifecycle (creation, invocation)
- Apply configured parameters to subagents

**Key Features**:
- Builds system prompts listing available subagents
- Creates runnable instances via `create_agent()`
- Provides `get_task_tool()` for main agent integration
- Filters and merges tools/middleware per configuration

## 5. Runtime Integration

**Location**: `src/components/deepagents/runtime.py`

**Function**: `create_deep_agent_runtime()`

**Integration Steps**:
```python
1. Create SubAgentMiddleware with:
   - Default model and tools
   - SubAgent specifications from factory
   - Default middleware stack

2. Get task tool from SubAgentMiddleware
3. Add task tool to main agent's tool list
4. Include SubAgentMiddleware in main agent's middleware stack
5. Build agent graph with create_agent()
```

## Recent Optimizations (2025-01-24)

### Refactoring: Modular SubAgents Structure

**Motivation**:
- Old `__init__.py` had 312 lines, violating KISS principle
- SubAgent classes mixed with other middleware
- Poor separation of concerns

**Changes**:
1. Created dedicated `runtime_middlewares/subagents/` folder
2. Separated types (`types.py`) from logic (`middleware.py`)
3. Removed 200+ lines from `__init__.py`
4. Updated all imports to new paths

**Before**:
```python
# src/components/deepagents/runtime_middlewares/__init__.py (312 lines)
class SubAgent: ...
class CompiledSubAgent: ...
class SubAgentMiddleware: ...
class PatchToolCallsMiddleware: ...
# All mixed together
```

**After**:
```python
# src/components/deepagents/runtime_middlewares/subagents/__init__.py (clean)
from .types import SubAgent, CompiledSubAgent
from .middleware import SubAgentMiddleware

# src/components/deepagents/runtime_middlewares/__init__.py (simplified)
# Only PatchToolCallsMiddleware and other core middleware
```

**Benefits**:
- **KISS**: Each module has clear, single purpose
- **SRP**: Types and logic separated
- **Maintainability**: Easier to navigate and modify
- **Testability**: Isolated components easier to test
- **OCP**: Can add new subagent features without touching core middleware

### Import Migration

**Updated Files**:
- `src/components/deepagents/runtime.py`
- `src/agents/deepagents/factories/base.py`
- `tests/unit/deepagents/test_subagent_parameter_flow.py`

**New Import Pattern**:
```python
from src.components.deepagents.runtime_middlewares.subagents import (
    SubAgent,
    CompiledSubAgent,
    SubAgentMiddleware,
)
```

## Configuration Flow Summary

```
1. JSON Config (subagents.json)
   ↓
2. SubAgentsProviderRegistry.get_subagent_config()
   ↓
3. BaseDeepAgentFactory._build_subagent_specs()
   ↓ (creates SubAgent instances)
4. SubAgentMiddleware._create_subagent_runnables()
   ↓ (builds runnable agents)
5. Main Agent Runtime (integrated via task tool)
```

## Key Design Principles

1. **Configuration-Driven**: All subagent behavior defined in JSON
2. **Parameter Categorization**: Clean separation of LLM, agent, runtime, display configs
3. **Factory Pattern**: Centralized subagent creation logic
4. **Middleware Pattern**: Non-invasive integration with main agent
5. **SOLID Principles**: Single responsibility, open/closed, dependency inversion

## Future Considerations

1. **Dynamic Subagent Loading**: Hot-reload configuration without restart
2. **Subagent Pools**: Reuse subagent instances for performance
3. **Custom Subagent Types**: User-defined subagents via plugins
4. **Monitoring**: Detailed metrics on subagent usage and performance

## Related Documentation

- `config/agents/deep/models/subagents.json` - Subagent configurations
- `src/core/providers/subagents_provider_registry.py` - Configuration provider
- `src/agents/deepagents/factories/base.py` - Factory implementation
- `src/components/deepagents/runtime_middlewares/subagents/` - Middleware implementation
- `tests/unit/deepagents/test_subagent_parameter_flow.py` - Unit tests

---

**Last Updated**: 2025-01-24
**Optimization**: Modular SubAgents Structure Refactoring
