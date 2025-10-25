# Agent Streaming and Safety Implementation

## Overview

This directory contains technical documentation for implementing streaming execution and safety mechanisms in the Multi-AI-Agent system.

## Documents

### 1. [Safety Mechanisms](./safety-mechanisms.md)

Comprehensive guide to preventing runaway agent execution and controlling resource consumption.

**Key Topics:**
- Execution timeout protection
- Recursion limit management
- Token consumption monitoring
- Cost control mechanisms

**Target:**
- Both Basic and Deep agent modes
- All provider configurations

### 2. [Deep Agent Streaming](./deep-agent-streaming.md)

Technical specification for migrating Deep agent from blocking execution to real-time streaming with human oversight.

**Key Topics:**
- Streaming implementation with `astream()`
- Real-time progress feedback
- Human-in-the-loop integration
- Event processing and display

**Target:**
- Deep agent mode only
- Basic mode remains with `ainvoke()`

## Implementation Strategy

### Phase 1: Safety First (Week 1)

**Priority: Critical**

Implement core safety mechanisms to prevent resource waste:
1. Add timeout protection to Deep agents
2. Reduce recursion limits to safe values
3. Test timeout behavior

**Files Modified:**
- `src/agents/deepagents/instances/base_deep_agent.py`
- `src/components/deepagents/runtime.py`
- `config/agents/deep/models/providers.json`

### Phase 2: Deep Agent Streaming (Week 2)

**Priority: High**

Replace blocking execution with transparent streaming:
1. Implement event processing in conversation handler
2. Add real-time tool call display
3. Show reasoning step progress
4. Display subagent delegations

**Files Modified:**
- `src/application/services/agent/deep/conversation.py`
- `src/agents/deepagents/instances/base_deep_agent.py`

### Phase 3: Human-in-the-Loop (Week 2-3)

**Priority: High**

Enable user approval for dangerous operations:
1. Configure HumanInTheLoopMiddleware
2. Implement interrupt handling
3. Add user prompt and decision logic
4. Test approval workflows

**Files Modified:**
- `src/components/deepagents/runtime.py`
- `src/application/services/agent/deep/conversation.py`

**Files Created:**
- `src/application/services/agent/deep/hitl_handler.py`

### Phase 4: Token Monitoring (Week 3)

**Priority: Medium**

Track and limit token consumption:
1. Create token tracking middleware
2. Implement budget enforcement
3. Add usage reporting
4. Test with different providers

**Files Created:**
- `src/components/deepagents/middlewares/token_limit.py`

**Files Modified:**
- `src/components/deepagents/runtime.py`
- `src/agents/deepagents/instances/base_deep_agent.py`

## Design Principles

### 1. Basic vs Deep Mode

**Basic Agent:**
- Remains with `ainvoke()` for simplicity
- Optimized for quick queries (<10s)
- Minimal overhead, fast response
- Suitable for simple tool-calling scenarios

**Deep Agent:**
- Migrates to `astream()` for visibility
- Handles complex, multi-step reasoning
- Real-time feedback essential
- Human oversight for safety

### 2. Safety First

All implementations prioritize:
- Preventing runaway costs
- Protecting user resources
- Graceful error handling
- Transparent operation

### 3. User Experience

Focus on:
- Real-time visibility
- Actionable feedback
- User control
- Trust building

### 4. Backward Compatibility

Changes are:
- Configuration-driven
- Non-breaking
- Opt-in where possible
- Gracefully degrading

## Configuration Schema

### Safety Configuration

```json
{
  "models": {
    "claude-4.5-sonnet": {
      "max_execution_time": 120,
      "max_recursion_limit": 50,
      "max_input_tokens": 100000,
      "max_output_tokens": 50000,
      "max_cost_usd": 1.0
    }
  }
}
```

### Streaming Configuration

```json
{
  "models": {
    "claude-4.5-sonnet": {
      "streaming_enabled": true,
      "show_reasoning_steps": true,
      "show_tool_calls": true,
      "show_subagent_delegations": true
    }
  }
}
```

### HITL Configuration

```json
{
  "models": {
    "claude-4.5-sonnet": {
      "hitl_enabled": true,
      "hitl_tools": [
        "write_file",
        "delete_file",
        "execute_shell",
        "edit_file"
      ]
    }
  }
}
```

## Testing Requirements

### Unit Tests

- Timeout mechanism behavior
- Stream event processing
- HITL decision handling
- Token tracking accuracy

### Integration Tests

- End-to-end streaming execution
- HITL approval workflows
- Multi-step reasoning visibility
- Subagent delegation display

### Performance Tests

- Streaming overhead measurement
- Token tracking performance
- Display update efficiency
- Large query handling

## Success Metrics

### Quantitative

- Timeout prevents >95% of runaway executions
- Streaming adds <5% overhead
- HITL reduces dangerous operations by >80%
- Token tracking accuracy >99%

### Qualitative

- Users report improved transparency
- Increased trust in agent operations
- Fewer unexpected costs
- Better understanding of agent behavior

## Timeline

- **Week 1:** Safety mechanisms implementation
- **Week 2:** Deep agent streaming
- **Week 2-3:** HITL integration
- **Week 3:** Token monitoring and polish
- **Week 4:** Testing and documentation

## Resources

### LangChain/LangGraph Documentation

- Streaming: https://python.langchain.com/docs/langgraph/how-tos/stream-values
- HITL: https://python.langchain.com/docs/langchain/agents/middleware#human-in-the-loop
- Interrupts: https://python.langchain.com/docs/langgraph/how-tos/interrupt

### Internal References

- Agent Architecture: `docs/refactoring/new_engine_architecture/`
- DeepAgents Design: `docs/deepagents-architecture/`
- Provider Configuration: `config/agents/deep/models/`

## Contact

For questions or clarifications, refer to the main project documentation or consult the development team.

