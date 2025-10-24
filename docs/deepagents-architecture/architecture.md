# DeepAgents Architecture

## Overview

DeepAgents is a multi-agent system implementation that extends the existing agent architecture to support complex, multi-step tasks through middleware, subagents, and advanced planning capabilities. This document outlines the overall architecture design and implementation strategy.

## Architecture Design

### 1. System Integration

DeepAgents integrates with the existing project architecture as a new agent mode within the agent engine:

```
Engine Types:
├── llm          # Direct LLM interaction
├── agent        # Agent-based interaction
│   ├── basic    # Single agent mode (existing)
│   └── deep     # Multi-agent mode (new)
├── agentflow    # Workflow-based agents
└── dify         # Dify integration
```

### 2. Core Components

#### 2.1 Middleware System

**Location**: `src/application/services/shared/middleware/`

The middleware system provides core functionality that can be shared across different agent types:

```
src/application/services/shared/middleware/
├── __init__.py
├── filesystem.py      # File system operations and memory
├── subagents.py      # Subagent management and communication
├── memory.py         # Advanced memory management
└── registry.py       # Middleware registration and discovery
```

**Key Features**:
- File system operations (read, write, edit, search)
- Long-term memory storage in `/memories/` directory
- Subagent lifecycle management
- State persistence and recovery

#### 2.2 DeepAgents Implementation

**Location**: `src/agents/deepagents/`

Following the same pattern as basicagents:

```
src/agents/deepagents/
├── __init__.py
├── managers/          # DeepAgents information and lifecycle
│   ├── __init__.py
│   └── deep_agent_manager.py
├── factories/         # DeepAgent creation factories
│   ├── __init__.py
│   ├── base.py
│   ├── zhipu_factory.py
│   ├── openai_factory.py
│   └── ollama_factory.py
├── adapters/          # Configuration parsing and adaptation
│   ├── __init__.py
│   ├── base.py
│   ├── zhipu_adapter.py
│   ├── openai_adapter.py
│   └── ollama_adapter.py
└── instances/         # Concrete DeepAgent implementations
    ├── __init__.py
    ├── base_deep_agent.py
    ├── zhipu_deep_agent.py
    ├── openai_deep_agent.py
    └── ollama_deep_agent.py
```

#### 2.3 Component System

**Location**: `src/components/deepagents/`

```
src/components/deepagents/
├── __init__.py
├── prompts/           # Prompt templates and management
│   ├── __init__.py
│   ├── registry.py
│   ├── deep_agent.md
│   ├── subagent.md
│   └── planning.md
└── subagents/        # Subagent configurations
    ├── __init__.py
    ├── research_agent.py
    ├── coding_agent.py
    └── analysis_agent.py
```

#### 2.4 Service Layer

**Location**: `src/application/services/agent/deep/`

```
src/application/services/agent/deep/
├── __init__.py
├── service.py         # DeepAgentService implementation
├── conversation.py    # Conversation handling
├── streaming.py       # Streaming response management
└── agent_lifecycle.py # Agent lifecycle management
```

## Configuration System

### 1. Provider Configuration

DeepAgents extends the existing provider configuration system in `src/core/providers/provider_registry.py`:

```json
{
  "providers": {
    "zhipu": {
      "default_model": "glm-4",
      "models": {
        "glm-4": {
          "name": "GLM-4",
          "description": "Zhipu GLM-4 model"
        }
      }
    }
  }
}
```

### 2. Middleware Configuration

Middleware configuration is hardcoded for simplicity, focusing on core functionality:

```python
# Hardcoded middleware configuration
DEFAULT_MIDDLEWARE = [
    "filesystem",  # File system operations
    "subagents"    # Subagent management
]
```

### 3. Subagent Configuration

Subagent configurations are stored in `src/components/deepagents/subagents/`:

```python
# Example: research_agent.py
RESEARCH_AGENT = {
    "name": "research-agent",
    "description": "Conducts thorough research on complex topics",
    "system_prompt": "You are a dedicated researcher...",
    "tools": ["internet_search", "file_read"],
    "model": "glm-4"
}
```

## Implementation Flow

### 1. Agent Creation Process

```
Provider Registry → DeepAgent Manager → Factory → Adapter → Instance
```

1. **Provider Registry**: Load LLM configurations from JSON
2. **Manager**: Filter and validate available LLMs for DeepAgents
3. **Factory**: Create DeepAgent instances based on provider
4. **Adapter**: Parse and adapt configuration parameters
5. **Instance**: Implement concrete DeepAgent with middleware

### 2. Service Integration

```
User Query → Service Router → DeepAgentService → DeepAgent Instance → Middleware → Response
```

1. **Service Router**: Route to DeepAgentService based on agent_type="deep"
2. **DeepAgentService**: Initialize and manage DeepAgent lifecycle
3. **DeepAgent Instance**: Execute query with middleware support
4. **Middleware**: Process through filesystem, subagents, memory
5. **Response**: Return processed result to user

## System Integration Points

### 1. Tool System Integration

- **Existing**: Reuse `UnifiedToolManager` for external tools
- **New**: Add middleware-provided tools (filesystem, subagents)
- **Combined**: DeepAgents have access to both external and middleware tools

### 2. Memory System Integration

- **Existing**: Reuse `GlobalMemoryManager` and `BaseAgentCheckpointer`
- **Extension**: Add filesystem-based long-term memory via middleware
- **Integration**: Unified memory access across basic and deep agents

### 3. Streaming System Integration

- **Purpose**: Real-time display of LLM responses for better user experience
- **Implementation**: Reuse existing streaming utilities from `src/llm/utils`
- **Extension**: Support streaming for subagent responses

### 4. Configuration System Integration

- **Base**: Extend `src/core/providers/provider_registry.py`
- **Middleware**: Hardcoded configuration for core functionality
- **Subagents**: File-based configuration in components directory

## Command Line Interface

### 1. Mode Switching

```bash
/mode basic    # Switch to basic agent mode
/mode deep     # Switch to deep agent mode
```

### 2. Existing Commands

```bash
/switch llm    # Switch LLM provider (existing)
/switch agent  # Switch agent provider (existing)
```

## Key Design Decisions

### 1. Middleware Location

**Decision**: Place middleware in `src/application/services/shared/middleware/`

**Rationale**: 
- Shared across different agent types
- Reusable for future langgraph native implementation
- Follows existing shared component pattern

### 2. Configuration Strategy

**Decision**: Hardcode core middleware, file-based subagent configs

**Rationale**:
- Simplicity for core functionality (filesystem, subagents)
- Flexibility for subagent configurations
- Easy to extend and modify

### 3. Service Architecture

**Decision**: Follow existing service pattern with DeepAgentService

**Rationale**:
- Consistent with existing architecture
- Easy integration with service router
- Maintains separation of concerns

### 4. Component Organization

**Decision**: Mirror basicagents structure for consistency

**Rationale**:
- Familiar development pattern
- Easy to understand and maintain
- Consistent with existing codebase

## Implementation Phases

### Phase 1: Core Infrastructure
- Implement middleware system
- Create basic DeepAgent structure
- Integrate with existing service router

### Phase 2: Middleware Implementation
- Filesystem middleware
- Subagent middleware
- Memory integration

### Phase 3: Service Layer
- DeepAgentService implementation
- Streaming integration
- Command line interface

### Phase 4: Advanced Features
- Planning middleware
- Advanced subagent management
- Performance optimization

## Future Extensions

### 1. Additional Middleware
- Planning middleware for complex task decomposition
- Communication middleware for inter-agent coordination
- Monitoring middleware for performance tracking

### 2. Advanced Subagent Features
- Dynamic subagent creation
- Subagent communication protocols
- Hierarchical subagent structures

### 3. Configuration Enhancements
- Runtime configuration updates
- A/B testing for subagent configurations
- Performance-based subagent selection

## Conclusion

This architecture provides a solid foundation for implementing DeepAgents while maintaining consistency with the existing codebase. The modular design allows for incremental implementation and future extensions while ensuring compatibility with existing systems.

