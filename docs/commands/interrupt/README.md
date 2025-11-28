# Keyboard Interrupt Mechanism Implementation

## Overview

This directory contains detailed implementation specifications for adding keyboard interrupt handling (Ctrl+C) to all three execution modes in the Multi-AI-Agent CLI application.

## Goal

Implement a double Ctrl+C mechanism across all modes:
- First Ctrl+C: Interrupt current operation, return to CLI prompt
- Second Ctrl+C (within 3 seconds): Exit application

## Documents

### 1. DeepAgent Interrupt Mechanism
**File**: [deepagent-interrupt-mechanism.md](deepagent-interrupt-mechanism.md)

**Scope**: LangGraph-based agent with stateful conversation management

**Key Features**:
- Interrupt during streaming agent execution
- Preserve conversation history (exclude interrupted message)
- Notify agent runtime using SystemMessage
- Persist clean checkpoint state

**Complexity**: High (requires state management and checkpoint coordination)

### 2. BasicAgent Interrupt Mechanism
**File**: [basicagent-interrupt-mechanism.md](basicagent-interrupt-mechanism.md)

**Scope**: LangChain AgentExecutor-based agent with stateless design

**Key Features**:
- Interrupt during agent tool execution
- No state persistence needed
- Simple cleanup and return to prompt

**Complexity**: Low (stateless, no checkpoint management)

### 3. LLM Interrupt Mechanism
**File**: [llm-interrupt-mechanism.md](llm-interrupt-mechanism.md)

**Scope**: Direct LLM streaming without agent framework

**Key Features**:
- Interrupt during streaming response
- Preserve and display partial response
- Performance metrics for partial content

**Complexity**: Medium (preserve partial streaming output)

## Implementation Order

Based on requirements, implement in this order:

1. **DeepAgent** (Priority: Highest)
   - Most complex implementation
   - Requires state management coordination
   - See: [deepagent-interrupt-mechanism.md](deepagent-interrupt-mechanism.md)

2. **BasicAgent** (Priority: Medium)
   - Simpler than DeepAgent
   - Can reuse main loop infrastructure
   - See: [basicagent-interrupt-mechanism.md](basicagent-interrupt-mechanism.md)

3. **LLM** (Priority: Low)
   - Independent streaming implementation
   - Partial response preservation
   - See: [llm-interrupt-mechanism.md](llm-interrupt-mechanism.md)

## Shared Infrastructure

### Main Loop Double Ctrl+C Handler

**File**: `src/application/cli/main.py`

All three modes share the same double-Ctrl+C logic in the main CLI loop:

```python
except KeyboardInterrupt:
    import time
    now = time.monotonic()

    if ctx.exit_hint_until and now < ctx.exit_hint_until:
        # Second press - exit
        if ctx.exit_hint_handle:
            ctx.exit_hint_handle.cancel()
        ctx.exit_hint_until = None
        ctx.console.print("\nGoodbye!", style=COLORS["info"])
        break
    else:
        # First press - set hint window
        EXIT_CONFIRM_WINDOW = 3.0
        ctx.exit_hint_until = now + EXIT_CONFIRM_WINDOW
        # ... timer setup
        ctx.console.print(
            "\n[yellow]Interrupted. Press Ctrl+C again within 3s to exit.[/]"
        )
        continue
```

### State Management

**File**: `src/application/cli/state.py`

Add interrupt tracking fields to `AppState`:

```python
class AppState:
    # Existing fields...

    # Interrupt handling
    exit_hint_until: Optional[float] = None
    exit_hint_handle: Optional[asyncio.TimerHandle] = None
```

## Reference Implementation

All implementations reference the official DeepAgents CLI:
- **Repository**: `deepagents/libs/deepagents-cli/`
- **Key files**:
  - `deepagents_cli/execution.py` - Agent interrupt handling
  - `deepagents_cli/input.py` - Double Ctrl+C keyboard binding
  - `deepagents_cli/config.py` - Session state management
  - `deepagents_cli/main.py` - Main loop integration

## Testing Strategy

### Common Test Scenarios

For all three modes:
1. Single Ctrl+C during execution - verify return to prompt
2. Double Ctrl+C (within 3s) - verify application exit
3. Double Ctrl+C (after 3s) - verify treated as two separate interrupts
4. Interrupt then immediate new query - verify clean state

### Mode-Specific Scenarios

**DeepAgent**:
- Interrupt during tool execution - verify checkpoint preservation
- Interrupt during streaming - verify state consistency
- Multiple interrupts in session - verify no state corruption

**BasicAgent**:
- Interrupt during tool call - verify clean exit
- Interrupt then retry - verify memory works correctly

**LLM**:
- Interrupt early in stream - verify minimal partial content
- Interrupt mid-stream - verify partial content displayed
- Interrupt with Unicode content - verify encoding fallback

## Dependencies

### Python Standard Library
- `asyncio` - Event loop and timer management
- `time.monotonic()` - Precise timing for double-press detection

### LangChain / LangGraph
- `agent.runtime.aupdate_state()` - DeepAgent state update (LangGraph)
- `agent.ainvoke()` - BasicAgent execution (LangChain)
- `BaseChatModel.astream()` - LLM streaming

### Project Components
- `AppState` - CLI session state
- `MemorySyncAdapter` - Conversation persistence
- `StreamingManager` - LLM streaming display

## Notes

- Each mode has different state management requirements
- The double-Ctrl+C mechanism is shared across all modes
- DeepAgent requires the most careful state handling
- LLM mode provides partial content even when interrupted
- All implementations maintain clean separation of concerns
