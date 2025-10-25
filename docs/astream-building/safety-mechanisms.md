# Agent Execution Safety Mechanisms

## Overview

This document describes the safety mechanisms designed to prevent runaway agent execution, excessive token consumption, and uncontrolled reasoning loops in both Basic and Deep agent modes.

## Current Issues

### 1. Lack of Timeout Protection

**Current State:**
- Both Basic and Deep agents use `ainvoke()` without time limits
- Deep agents can reason indefinitely on complex problems
- No mechanism to terminate long-running executions
- Users experience unresponsive CLI with no feedback

**Impact:**
- Deep agent can run for minutes without user awareness
- Excessive API costs from prolonged reasoning
- Poor user experience during extended operations

### 2. Excessive Recursion Limits

**Current Configuration:**
```python
# src/components/deepagents/runtime.py
return agent_graph.with_config({"recursion_limit": 1000})
```

**Problems:**
- Recursion limit of 1000 is unreasonably high
- Allows agent to loop through 1000 reasoning steps
- No practical benefit beyond ~50 steps
- Increases risk of infinite reasoning loops

### 3. No Token Consumption Monitoring

**Current State:**
- No tracking of input/output tokens across agent execution
- No cost estimation or budget limits
- Users unaware of token usage until API bill arrives
- No warnings when approaching spending limits

**Impact:**
- Unexpected API costs
- Potential bill shock for complex queries
- No ability to set per-query budgets

## Proposed Solutions

### Solution 1: Execution Timeout

#### Implementation Approach

Add timeout protection at the agent invocation level using `asyncio.wait_for()`.

**Target Files:**
- `src/agents/deepagents/instances/base_deep_agent.py`
- `src/agents/basicagents/instances/base_agent.py` (optional)

**Key Changes:**
1. Add `max_execution_time` parameter to agent initialization
2. Wrap `ainvoke()`/`astream()` calls with timeout
3. Return graceful error message on timeout
4. Log timeout events for monitoring

**Configuration:**
- Default timeout: 120 seconds (2 minutes)
- Configurable per provider/model in config files
- Override-able per query execution

#### Error Handling

On timeout:
- Return structured error response
- Include elapsed time and reasoning steps completed
- Suggest query simplification to user
- Log timeout event with context

### Solution 2: Reduced Recursion Limits

#### Implementation Approach

Lower recursion limits to practical values based on agent complexity.

**Recommended Limits:**
- Basic Agent: 25 steps (typical tool-calling loops)
- Deep Agent: 50 steps (allows for complex reasoning)
- Subagents: 30 steps (focused task execution)

**Rationale:**
- 99% of queries complete within these limits
- Prevents infinite loops
- Forces agent to be more efficient
- Maintains quality while adding safety

**Configuration Location:**
```
config/agents/deep/models/providers.json
config/agents/basic/models/providers.json
```

### Solution 3: Token Consumption Monitoring

#### Implementation Approach

Create middleware to track and limit token usage across agent execution.

**Key Components:**

1. **Token Tracking Middleware**
   - Intercepts all LLM calls
   - Records input/output tokens
   - Accumulates totals per query
   - Estimates cost based on model pricing

2. **Budget Enforcement**
   - Set maximum input token limit (default: 100,000)
   - Set maximum output token limit (default: 50,000)
   - Set maximum cost limit (default: $1.00 USD)
   - Raise error when limit exceeded

3. **Usage Reporting**
   - Display token usage after query completion
   - Show estimated cost
   - Warn when approaching limits
   - Log usage statistics for analysis

**Target Files:**
- `src/components/deepagents/middlewares/token_limit.py` (new)
- `src/components/deepagents/runtime.py`
- `src/agents/deepagents/instances/base_deep_agent.py`

#### Usage Statistics Format

After query completion, display:
- Total input tokens used
- Total output tokens used
- Estimated cost
- Percentage of budget consumed

### Solution 4: Progress Monitoring

#### Implementation Approach

For Deep agents using streaming, track and display progress metrics.

**Tracked Metrics:**
- Number of reasoning steps taken
- Number of tool calls made
- Elapsed time
- Token consumption (if available)

**Display Format:**
- Real-time step counter: "Step 15/50..."
- Tool call notifications: "Calling: read_file"
- Time elapsed: "Elapsed: 45s"

**Early Termination:**
- Detect apparent infinite loops (repeated identical actions)
- Allow user to cancel with Ctrl+C
- Provide option to continue or abort on warnings

## Implementation Priority

### Phase 1: Critical Safety (Week 1)
1. Add timeout mechanism to Deep agents
2. Reduce recursion limits to safe values
3. Test timeout behavior with various queries

### Phase 2: Monitoring (Week 2)
4. Implement basic token counting middleware
5. Add usage reporting to query results
6. Test with different model providers

### Phase 3: Advanced Features (Week 3)
7. Implement budget enforcement
8. Add progress monitoring for streaming
9. Implement early termination detection

## Configuration Schema

### Provider Configuration

```json
{
  "research": {
    "providers": {
      "ANTHROPIC": {
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
    }
  }
}
```

### Runtime Override

Allow per-query overrides:
```python
result = await agent.ainvoke(
    query,
    session_id=session_id,
    timeout=180,  # Override default
    max_tokens=150000  # Override default
)
```

## Testing Strategy

### Timeout Testing
- Test with intentionally slow operations
- Verify graceful error handling
- Confirm timeout accuracy within 5%

### Recursion Limit Testing
- Create queries that require many steps
- Verify execution stops at limit
- Confirm appropriate error message

### Token Monitoring Testing
- Execute queries with known token counts
- Verify accuracy of tracking
- Test budget enforcement triggers

## Monitoring and Logging

### Logged Events

1. **Timeout Events**
   - Query that timed out
   - Elapsed time
   - Steps completed
   - Session ID

2. **Recursion Limit Events**
   - Query that hit limit
   - Final step count
   - Last action taken
   - Session ID

3. **Token Budget Events**
   - Query that exceeded budget
   - Total tokens consumed
   - Estimated cost
   - Session ID

### Log Format

```
[TIMEOUT] session=abc123 elapsed=120.5s steps=45 query="..."
[RECURSION_LIMIT] session=abc123 steps=50 last_action="tool_call:read_file"
[TOKEN_LIMIT] session=abc123 tokens=105000 cost=$1.23
```

## Performance Impact

### Expected Overhead

- Timeout mechanism: Negligible (<1ms)
- Token counting: Minimal (~2-5ms per LLM call)
- Progress monitoring: Negligible (async operations)

### Benefits

- Prevents runaway costs
- Improves user experience
- Enables better resource planning
- Provides operational insights

## Backward Compatibility

All safety mechanisms are:
- Opt-in via configuration
- Backward compatible with existing code
- Non-breaking for current functionality
- Gracefully degrading if disabled

## References

- LangGraph timeout configuration: `RunnableConfig["timeout"]`
- AsyncIO wait_for: `asyncio.wait_for(coro, timeout)`
- LangChain middleware: `AgentMiddleware.wrap_model_call()`

