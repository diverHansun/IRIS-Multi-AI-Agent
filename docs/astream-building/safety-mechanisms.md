# Safety Mechanisms

Safety controls to prevent excessive resource consumption and runaway execution in Deep Agent mode.

## 1. Current State

### Existing Controls

**LangGraph recursion limit:**
```python
# src/components/deepagents/runtime.py
agent_graph.with_config({"recursion_limit": 1000})
```
- Limits graph execution steps
- Current value: 1000 (very high)
- No time-based limit

**Checkpointer:**
- Saves state after each node
- Enables recovery from interrupts
- Already implemented

### Missing Controls

1. **No execution timeout** - Agent can run indefinitely
2. **No token consumption monitoring** - No visibility into costs
3. **No cost limits** - Could exceed budget
4. **High recursion limit** - 1000 steps is excessive for most tasks

## 2. Timeout Mechanism

### Implementation Strategy

**Use `asyncio.wait_for` wrapper:**
```python
# src/application/services/agent/deep/conversation.py

import asyncio

async def handle_deep_agent_query(ctx, query: str) -> str:
    timeout = config.get("max_execution_time", 120)  # seconds
    
    try:
        result = await asyncio.wait_for(
            _execute_streaming_query(ctx, query),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        ctx.console.print(f"[red]Execution timeout after {timeout}s[/]")
        return ""
```

### Configuration

**In `providers.json`:**
```json
{
  "models": {
    "claude-4.5-sonnet": {
      "max_execution_time": 120,
      "max_recursion_limit": 50
    }
  }
}
```

**Default values:**
- Main agent: 120 seconds
- Subagents: 90 seconds (shorter than main)

### Timeout Behavior

**When timeout occurs:**
1. Stop streaming immediately
2. Display timeout message with elapsed time
3. Return partial results (optional)
4. Save conversation state
5. Allow user to retry or adjust query

## 3. Recursion Limit

### Current Problem

**1000 steps is too high:**
- Most tasks complete in < 20 steps
- Allows infinite loops to run too long
- Consumes excessive tokens

### Recommended Limits

| Agent Type | Recursion Limit | Rationale |
|------------|----------------|-----------|
| Main Deep Agent | 50 | Sufficient for complex tasks |
| Subagents | 30 | Focused, specific tasks |
| Basic Agent | 15 | Simple tool-calling workflows |

### Implementation

**In `runtime.py`:**
```python
# Read from config instead of hardcoded
recursion_limit = model_settings.get("max_recursion_limit", 50)
agent_graph = agent_graph.with_config({"recursion_limit": recursion_limit})
```

**Behavior when limit reached:**
- LangGraph raises exception
- Display: "Recursion limit reached after N steps"
- Suggest: "Try breaking down the task or increasing limit"

## 4. Token Consumption Monitoring

### Tracking Strategy

**Monitor at three levels:**
1. **Per-step tracking** - Tokens used in each reasoning step
2. **Session tracking** - Total tokens in current session
3. **Cost estimation** - Approximate USD cost

### Implementation

**Token counter middleware:**
```python
# src/components/deepagents/middlewares/token_monitor.py

class TokenMonitorMiddleware(AgentMiddleware):
    def __init__(self, max_input_tokens=100000, max_output_tokens=50000):
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.input_tokens = 0
        self.output_tokens = 0
    
    def after_model(self, state, runtime):
        # Extract token usage from last message
        usage = self._extract_usage(state["messages"][-1])
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        
        # Check limits
        if self.input_tokens > self.max_input_tokens:
            raise TokenLimitExceeded("Input token limit exceeded")
        if self.output_tokens > self.max_output_tokens:
            raise TokenLimitExceeded("Output token limit exceeded")
```

### Display During Execution

**Show token usage in progress:**
```
  Step 5 | 12.3s | Generating response...
    -> Tokens: 1,234 input / 567 output (~$0.02)
```

**Show summary at end:**
```
Summary:
  - Total tokens: 15,234 input / 8,901 output
  - Estimated cost: $0.18
  - Average per step: 2,539 tokens
```

### Configuration

**In `providers.json`:**
```json
{
  "models": {
    "claude-4.5-sonnet": {
      "max_input_tokens": 100000,
      "max_output_tokens": 50000,
      "max_cost_usd": 1.0,
      "token_pricing": {
        "input_per_million": 3.0,
        "output_per_million": 15.0
      }
    }
  }
}
```

## 5. Error Handling

### Error Types

**Timeout errors:**
```python
except asyncio.TimeoutError:
    return {
        "success": False,
        "error": "timeout",
        "output": f"Execution timeout after {timeout}s",
        "elapsed_time": timeout
    }
```

**Token limit errors:**
```python
except TokenLimitExceeded as e:
    return {
        "success": False,
        "error": "token_limit",
        "output": str(e),
        "tokens_used": monitor.get_usage()
    }
```

**Recursion limit errors:**
```python
except RecursionError:
    return {
        "success": False,
        "error": "recursion_limit",
        "output": f"Recursion limit ({limit}) reached",
        "steps_completed": step_count
    }
```

**User interrupt:**
```python
except KeyboardInterrupt:
    return {
        "success": False,
        "error": "user_cancelled",
        "output": "Execution interrupted by user",
        "partial_result": current_output
    }
```

### Partial Results

**When execution stops early:**
- Save partial conversation to memory (optional)
- Display what was accomplished
- Show why execution stopped
- Suggest next steps

**Example:**
```
[yellow]Execution interrupted after 3 steps[/]

Partial progress:
  - Read configuration file
  - Analyzed structure
  - Started generating report (incomplete)

Reason: User interrupt (Ctrl+C)

You can:
  - Resume with a more specific query
  - Adjust timeout in config
  - Break task into smaller steps
```

## 6. Configuration Priority

### Priority Hierarchy

```
1. Runtime parameters (highest)
   await agent.ainvoke(query, timeout=180)

2. Model config
   config/agents/deep/models/providers.json

3. Default values (lowest)
   Hardcoded in code
```

### Override Examples

**Temporary override for specific query:**
```python
# In conversation handler
timeout = 300  # 5 minutes for complex task
result = await asyncio.wait_for(execute_query(...), timeout=timeout)
```

**Per-model defaults:**
```json
{
  "claude-4.5-sonnet": {
    "max_execution_time": 120
  },
  "qwen3-coder": {
    "max_execution_time": 180  // Longer for coding tasks
  }
}
```

## 7. Safety Summary

### Protection Layers

| Layer | Type | Trigger | Action |
|-------|------|---------|--------|
| **Timeout** | Time-based | After N seconds | Stop execution |
| **Recursion Limit** | Step-based | After N steps | Raise error |
| **Token Limit** | Resource-based | After N tokens | Stop execution |
| **User Interrupt** | Manual | Ctrl+C | Graceful stop |
| **HITL** | Manual | Dangerous tool | Wait for approval |

### Recommended Defaults

```json
{
  "max_execution_time": 120,
  "max_recursion_limit": 50,
  "max_input_tokens": 100000,
  "max_output_tokens": 50000,
  "max_cost_usd": 1.0
}
```

### Monitoring Commands

**View current limits:**
```bash
/config show safety
```

**Adjust limits:**
```bash
/config set max_execution_time 180
/config set max_recursion_limit 100
```

**View token usage:**
```bash
/session stats
```

## 8. Implementation Priority

| Priority | Feature | Complexity | Impact |
|----------|---------|------------|--------|
| P0 | Timeout mechanism | Low | High |
| P0 | Reduce recursion limit | Low | Medium |
| P1 | Token monitoring | Medium | Medium |
| P1 | Cost estimation | Low | Low |
| P2 | Partial result saving | Medium | Low |
| P2 | Configuration commands | Low | Low |

## 9. Testing Strategy

### Test Scenarios

**Timeout test:**
```python
# Query that takes > 120s
"Analyze all files in this large repository"
# Expected: Timeout after 120s with message
```

**Recursion test:**
```python
# Query that causes many steps
"Keep refining this code until perfect"
# Expected: Stop after 50 steps with message
```

**Token test:**
```python
# Query with large context
"Summarize these 100 documents"
# Expected: Monitor shows token usage, stops if limit exceeded
```

**Interrupt test:**
```python
# Start long-running query, press Ctrl+C
# Expected: Graceful stop with partial results
```

### Success Criteria

- Timeout triggers within 1 second of limit
- Recursion limit stops execution cleanly
- Token monitoring shows accurate counts
- User interrupt stops within 2 seconds
- All errors return proper error format
- Partial results are saved when appropriate
