# Deep Agent Streaming Implementation

## Overview

This document describes the migration of Deep agent mode from blocking `ainvoke()` to streaming `astream()` execution, including real-time progress feedback and human-in-the-loop integration.

## Current Issues

### 1. Black Box Execution

**Current Implementation:**
```python
# src/application/services/agent/deep/conversation.py
with ctx.console.status("[dim]Deep agent reasoning...[/]"):
    result = await agent.ainvoke(query, session_id=ctx.session_id)
```

**Problems:**
- Agent reasoning is completely invisible to user
- Only shows spinner: "Deep agent reasoning..."
- No indication of tool calls, reasoning steps, or subagent delegations
- User has no insight into what the agent is doing
- Cannot interrupt or provide feedback during execution

**Impact:**
- Poor user experience
- No visibility into long-running operations
- Difficult to debug agent behavior
- Users lose trust when agent takes long time

### 2. No Human-in-the-Loop Support

**Current State:**
- No mechanism for user approval of dangerous operations
- Tools like `write_file`, `delete_file` execute without confirmation
- No ability for user to edit tool parameters before execution
- No option to reject proposed actions

**Impact:**
- Safety concerns for file system operations
- Risk of unintended modifications
- Cannot enforce approval workflows
- Limited user control over agent actions

### 3. Lack of Real-time Feedback

**Current State:**
- Tool calls only reported after full completion
- Subagent delegations invisible during execution
- No progress indication for multi-step reasoning
- Cannot estimate time to completion

**Impact:**
- User uncertainty during long operations
- Cannot assess if agent is stuck
- Difficult to understand agent's approach
- No opportunity for early intervention

## Proposed Solution: Streaming with HITL

### Why Basic Agent Stays with ainvoke

**Design Decision:**
- Basic agent targets simpler, faster queries
- Typically completes in <10 seconds
- Less complex reasoning with fewer tool calls
- Streaming overhead not justified for quick operations
- Maintains simpler code path for basic use case

**Trade-offs:**
- Basic mode: Faster execution, less visibility
- Deep mode: Slower but transparent, controllable

### Architecture Changes

#### 1. Replace ainvoke with astream

**Target File:** `src/application/services/agent/deep/conversation.py`

**Current Flow:**
```
User Query -> ainvoke() -> Wait -> Final Result -> Display
```

**New Flow:**
```
User Query -> astream() -> Stream Events -> Real-time Display -> Final Result
```

**Stream Modes Used:**
- `updates`: Node-level updates (agent decisions, tool calls)
- `messages`: Token-level streaming (optional, for typing effect)

#### 2. Event Processing

**Event Types to Handle:**

1. **Agent Node Events**
   - Agent makes decision
   - Tool calls proposed
   - Reasoning step completed

2. **Tool Node Events**
   - Tool execution started
   - Tool result received
   - Tool execution time

3. **Subagent Events**
   - Task delegation to subagent
   - Subagent completion
   - Subagent result summary

#### 3. Real-time Display

**Display Strategy:**

1. **Progress Indicators**
   - Step counter: "Step 15/50"
   - Time elapsed: "45s elapsed"
   - Current action: "Reading file..."

2. **Tool Call Notifications**
   - Tool name and abbreviated arguments
   - Execution status (pending/complete/error)
   - Result preview (first 100 chars)

3. **Subagent Delegations**
   - Subagent type (research/coding/analysis)
   - Task description
   - Delegation status

**Output Format:**
```
Deep agent reasoning...
  Step 1: Analyzing query...
  Step 2: Calling tool: read_file(path="config.json")
    -> Result: {"api_key": "...", ...}
  Step 3: Delegating to subagent: research
    -> Task: Analyze configuration structure
  Step 4: Synthesizing results...

DeepAgent > [Final response]
```

### Human-in-the-Loop Integration

#### 1. Configuration

**Tools Requiring Approval:**

Define in configuration which tools need human approval:
```json
{
  "hitl_tools": [
    "write_file",
    "delete_file",
    "execute_shell",
    "edit_file"
  ]
}
```

**Approval Modes:**
- `approve`: Allow execution as proposed
- `edit`: Modify parameters before execution
- `reject`: Cancel execution with reason

#### 2. Implementation Approach

**Middleware Integration:**

Use LangChain's built-in `HumanInTheLoopMiddleware`:
- Already implemented in LangChain
- Integrates with `interrupt()` mechanism
- Supports approve/edit/reject decisions

**Configuration in Runtime:**
```python
# src/components/deepagents/runtime.py
interrupt_on = {
    "write_file": InterruptOnConfig(
        allowed_decisions=["approve", "edit", "reject"],
        description="File write operation requires approval"
    ),
    "delete_file": InterruptOnConfig(
        allowed_decisions=["approve", "reject"],
        description="File deletion requires confirmation"
    )
}
```

#### 3. Interrupt Handling

**Detection:**
- Stream will emit interrupt event
- Event contains tool call details
- Includes allowed decision types

**User Prompt:**
```
Tool execution requires approval:
  Tool: write_file
  Arguments:
    path: "config.json"
    content: "..."
  
Choose action:
  [A]pprove / [E]dit / [R]eject (default: Approve):
```

**Response Handling:**
- Parse user decision
- Modify tool call if edited
- Resume execution with decision
- Handle rejection gracefully

#### 4. Resumption

After user decision:
- Agent continues from interrupt point
- No state loss or restart needed
- Uses LangGraph's checkpoint mechanism
- Seamless continuation of reasoning

### Implementation Details

#### Stream Event Processing

**Event Structure:**
```python
async for event in agent.runtime.astream(input, config, stream_mode="updates"):
    # event format: {node_name: update_data}
    for node_name, update_data in event.items():
        if node_name == "agent":
            # Handle agent reasoning update
            process_agent_update(update_data)
        elif node_name == "tools":
            # Handle tool execution update
            process_tool_update(update_data)
        elif node_name == "__interrupt__":
            # Handle human-in-the-loop request
            decision = await prompt_user(update_data)
            await resume_execution(decision)
```

#### Progress Tracking

**Metrics to Track:**
- Reasoning step count
- Tool calls made
- Subagent delegations
- Elapsed time
- Estimated progress (if possible)

**Display Updates:**
- Update on each agent reasoning step
- Show tool calls immediately when proposed
- Display tool results when received
- Indicate subagent delegation and completion

#### Error Handling

**Timeout Integration:**
- Streaming respects timeout limits
- Gracefully cancel stream on timeout
- Display partial results if available
- Indicate timeout cause to user

**Stream Interruption:**
- Handle Ctrl+C gracefully
- Save partial progress
- Allow resumption if desired

### Configuration Schema

#### Deep Agent Configuration

```json
{
  "research": {
    "providers": {
      "ANTHROPIC": {
        "models": {
          "claude-4.5-sonnet": {
            "streaming_enabled": true,
            "show_reasoning_steps": true,
            "show_tool_calls": true,
            "show_subagent_delegations": true,
            "hitl_enabled": true,
            "hitl_tools": [
              "write_file",
              "delete_file",
              "execute_shell"
            ]
          }
        }
      }
    }
  }
}
```

### Code Changes Summary

#### Modified Files

1. **src/application/services/agent/deep/conversation.py**
   - Replace `ainvoke()` with `astream()`
   - Add event processing loop
   - Implement real-time display logic
   - Add HITL prompt and response handling

2. **src/components/deepagents/runtime.py**
   - Add `interrupt_on` configuration
   - Configure `HumanInTheLoopMiddleware`
   - Pass HITL config to agent creation

3. **src/agents/deepagents/instances/base_deep_agent.py**
   - Add streaming support parameters
   - Maintain backward compatibility
   - Add timeout wrapper

#### New Files

1. **src/application/services/agent/deep/hitl_handler.py** (optional)
   - User prompt logic
   - Decision parsing
   - Response formatting
   - Interrupt resumption

### Testing Strategy

#### Streaming Tests

1. **Basic Streaming**
   - Verify events received in real-time
   - Confirm correct event ordering
   - Validate event data completeness

2. **Tool Call Display**
   - Test with various tools
   - Verify parameter display
   - Confirm result preview

3. **Subagent Display**
   - Test delegation visibility
   - Verify task description shown
   - Confirm completion notification

#### HITL Tests

1. **Interrupt Detection**
   - Verify interrupt triggered for configured tools
   - Confirm correct tool details displayed
   - Test with multiple simultaneous tool calls

2. **Decision Handling**
   - Test approve flow
   - Test edit flow with parameter modification
   - Test reject flow with reason

3. **Resumption**
   - Verify execution continues after approval
   - Confirm state preservation
   - Test error handling on rejection

### User Experience

#### Expected Improvements

1. **Transparency**
   - Users see what agent is doing
   - Understand reasoning process
   - Track progress of long operations

2. **Control**
   - Approve dangerous operations
   - Modify parameters before execution
   - Cancel unwanted actions

3. **Confidence**
   - Trust agent with visibility
   - Learn agent capabilities
   - Identify when to intervene

4. **Efficiency**
   - Catch errors early
   - Redirect agent when off-track
   - Avoid costly mistakes

### Performance Considerations

#### Streaming Overhead

- Network: Minimal (events are small)
- Processing: Low (simple event parsing)
- Display: Negligible (async console output)

#### HITL Impact

- Only active for configured tools
- No overhead when not triggered
- User wait time is acceptable for safety

### Migration Path

#### Phase 1: Basic Streaming
- Implement event processing
- Add tool call display
- Show reasoning steps

#### Phase 2: Enhanced Display
- Add progress indicators
- Implement time tracking
- Show subagent delegations

#### Phase 3: HITL Integration
- Configure interrupt middleware
- Implement user prompts
- Add decision handling

#### Phase 4: Polish
- Improve display formatting
- Add color coding
- Optimize performance

### Backward Compatibility

- Configuration flags control streaming behavior
- Can disable streaming if needed
- Falls back to ainvoke if stream fails
- Maintains same return format

### Future Enhancements

1. **Token-level Streaming**
   - Enable typing effect for responses
   - Use `stream_mode="messages"`
   - Optional feature for enhanced UX

2. **Visual Progress Bar**
   - Rich progress bar for long operations
   - Estimated time remaining
   - Visual step indicator

3. **Interrupt Presets**
   - Pre-defined approval workflows
   - User preferences for tool approval
   - Smart auto-approval for trusted tools

4. **Streaming Logs**
   - Save streaming output to file
   - Replay execution for debugging
   - Export execution trace

## References

- LangGraph streaming API: `CompiledStateGraph.astream()`
- LangGraph stream modes: `"values"`, `"updates"`, `"messages"`
- LangChain HITL: `HumanInTheLoopMiddleware`
- LangGraph interrupts: `interrupt()` function

