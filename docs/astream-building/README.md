# Deep Agent Streaming & Safety Implementation

Documentation for implementing streaming output and safety mechanisms in Deep Agent mode.

## Documentation Structure

| Document | Description |
|----------|-------------|
| **deep-agent-streaming.md** | Streaming output and HITL implementation |
| **safety-mechanisms.md** | Timeout, token limits, and safety controls |
| **configuration-guide.md** | Configuration reference |
| **implementation-guide.md** | Implementation steps and file checklist |

## Current Issues

### Deep Agent Mode Problems
1. **Black Box Execution**: No visibility into reasoning process
2. **No Human-in-the-Loop**: Dangerous operations execute without approval
3. **No Safety Controls**: No timeout or token consumption limits
4. **Memory Not Integrated**: Global memory not properly configured

### Basic Agent Mode (Working)
- Uses `ainvoke` with complete memory integration
- Has checkpointer for state persistence
- Works as expected but lacks transparency

## Solution Overview

### Core Changes
1. **Replace `ainvoke` with `astream`** in Deep Agent mode only
2. **Implement Session-based HITL** with 4-option user interaction
3. **Add Safety Mechanisms**: timeout, recursion limit, token monitoring
4. **Fix Memory Integration**: properly configure checkpointer and global memory

### Key Principles
- Basic Agent mode remains unchanged (uses `ainvoke`)
- Deep Agent streaming maintains same return format
- HITL preferences are session-scoped (cleared on session end)
- Dangerous tools never allow auto-approval
- Terminal uses `ctx.console` with `asyncio.to_thread` for consistency

## Quick Navigation

- **Understanding Streaming?** → `deep-agent-streaming.md` Section 1
- **How HITL Works?** → `deep-agent-streaming.md` Section 2
- **Safety Configuration?** → `safety-mechanisms.md` Section 1
- **Configuration Options?** → `configuration-guide.md`
- **Implementation Steps?** → `implementation-guide.md`

## Architecture Layers

```
User Input
    ↓
Application Layer (conversation.py)
    ↓ astream() with event handling
Agent Instance (base_deep_agent.py)
    ↓ runtime.astream()
LangGraph CompiledStateGraph
    ↓ streaming events
Event Handler → Display progress
    ↓ on __interrupt__
HITL Handler → User decision
    ↓ decision
Resume execution
    ↓
Final Result
```

## Implementation Priority

| Priority | Task | Status |
|----------|------|--------|
| P0 | Implement astream in Deep Agent | Planned |
| P0 | Implement HITL with 4 options | Planned |
| P0 | Add timeout mechanism | Planned |
| P0 | Fix global memory integration | Planned |
| P1 | Add token consumption monitoring | Planned |
| P1 | Optimize progress display | Planned |
| P2 | Add session HITL commands | Planned |
