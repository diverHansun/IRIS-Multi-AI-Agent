# Implementation Guide

Step-by-step guide for implementing streaming and safety mechanisms in Deep Agent mode.

## 1. Implementation Overview

### Scope

**Changes to Deep Agent mode only:**
- Replace `ainvoke` with `astream`
- Add HITL with session-scoped preferences
- Implement safety mechanisms
- Fix global memory integration

**Basic Agent mode unchanged:**
- Continues using `ainvoke`
- Existing memory integration preserved
- No modifications needed

### Implementation Phases

| Phase | Tasks | Priority | Estimated Effort |
|-------|-------|----------|------------------|
| **Phase 1** | Core streaming + HITL | P0 | 2-3 days |
| **Phase 2** | Safety mechanisms | P0 | 1-2 days |
| **Phase 3** | Memory integration fix | P0 | 1 day |
| **Phase 4** | Token monitoring | P1 | 1-2 days |
| **Phase 5** | Commands & polish | P2 | 1 day |

## 2. File Modification Checklist

### Core Logic Files (Modify)

```
src/agents/deepagents/instances/base_deep_agent.py
  - Modify invoke() method to use astream
  - Maintain same return format
  - Add event collection logic

src/application/services/agent/deep/conversation.py
  - Replace ainvoke call with streaming handler
  - Add event processing loop
  - Integrate HITL handler
  - Add interrupt handling

src/agents/deepagents/factories/base.py
  - Fix checkpointer initialization
  - Pass global_memory_manager properly
  
src/components/deepagents/runtime.py
  - Make recursion_limit configurable
  - Read from model_settings
```

### New Files (Create)

```
src/application/services/agent/deep/event_handler.py
  - DeepAgentEventHandler class
  - Process streaming events
  - Display progress information

src/application/services/agent/deep/hitl_handler.py
  - handle_hitl_interrupt() function
  - 4-option user interaction
  - Integration with SessionHITLManager

src/application/services/agent/deep/session_hitl_manager.py
  - SessionHITLManager class
  - Session-scoped preference storage
  - Dangerous tools validation

src/components/deepagents/middlewares/token_monitor.py (optional, P1)
  - TokenMonitorMiddleware class
  - Track token consumption
  - Enforce token limits
```

### Configuration Files (Modify)

```
config/agents/deep/models/providers.json
  - Add streaming configuration
  - Add safety limits
  - Add HITL configuration

config/agents/deep/models/subagents.json
  - Add safety limits
  - Set streaming_enabled: false
```

### State Management (Modify)

```
src/application/cli/state.py
  - Add hitl_manager field to AppState

src/application/cli/main.py
  - Initialize SessionHITLManager
  - Load dangerous tools from config
```

## 3. Phase 1: Core Streaming + HITL

### Step 1.1: Create SessionHITLManager

**File:** `src/application/services/agent/deep/session_hitl_manager.py`

**Key methods:**
- `is_auto_approved(tool_name)` - Check if tool is auto-approved
- `can_auto_approve(tool_name)` - Check if tool allows auto-approval
- `add_auto_approve(tool_name)` - Add to session preferences
- `clear()` - Clear all preferences

### Step 1.2: Create HITL Handler

**File:** `src/application/services/agent/deep/hitl_handler.py`

**Key function:**
```python
async def handle_hitl_interrupt(
    ctx,
    interrupt_data: Dict[str, Any],
    hitl_config: Optional[Dict[str, Any]] = None
) -> Dict:
    # Process action_requests
    # Show 4-option prompt
    # Handle user decision
    # Return decisions dict
```

### Step 1.3: Modify BaseDeepAgent.invoke()

**File:** `src/agents/deepagents/instances/base_deep_agent.py`

**Changes:**
```python
async def invoke(self, query: str, *, session_id: str = "default", **kwargs) -> Dict[str, Any]:
    # Prepare input
    messages = [HumanMessage(content=query)]
    config = {"configurable": {"thread_id": session_id}}
    
    # Initialize collectors
    tool_calls = []
    tool_names = []
    subagent_calls = []
    final_output = ""
    
    # Stream events
    async for event in self.runtime.astream(
        {"messages": messages},
        config=config,
        stream_mode="updates"
    ):
        # Collect information from events
        # (Detailed processing in conversation.py)
        pass
    
    # Return same format as before
    return {
        "success": True,
        "output": final_output,
        "messages": all_messages,
        "tool_calls": len(tool_calls),
        "tool_names": tool_names,
        "subagent_calls": subagent_calls,
        "session_id": session_id
    }
```

### Step 1.4: Update Conversation Handler

**File:** `src/application/services/agent/deep/conversation.py`

**Changes:**
```python
async def handle_deep_agent_query(ctx, query: str) -> str:
    # Get config and agent
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")
    hitl_config = config.get("hitl_config", {})
    
    # Prepare input
    input_messages = {"messages": [HumanMessage(content=query)]}
    run_config = {"configurable": {"thread_id": ctx.session_id}}
    
    # Initialize tracking
    start_time = time.time()
    reasoning_steps = 0
    
    # Stream events
    async for event in agent.runtime.astream(input_messages, run_config, stream_mode="updates"):
        for node_name, update_data in event.items():
            if node_name == "agent":
                reasoning_steps += 1
                elapsed = time.time() - start_time
                ctx.console.print(f"  Step {reasoning_steps} | {elapsed:.1f}s | Processing...")
                # Handle tool calls display
            
            elif node_name == "tools":
                # Display tool results
                pass
            
            elif node_name == "__interrupt__":
                # Handle HITL
                decision = await handle_hitl_interrupt(ctx, update_data, hitl_config)
                # Send decision back (implementation depends on LangGraph API)
    
    # Display final result
    ctx.console.print(f"\n[bold blue]DeepAgent >[/] {final_output}")
    
    # Save to memory
    if ctx.global_memory:
        ctx.global_memory.add_conversation(ctx.session_id, query, final_output)
    
    return final_output
```

### Step 1.5: Initialize HITL Manager

**File:** `src/application/cli/main.py`

**Changes:**
```python
def _initialize_memory(ctx: AppState) -> None:
    # Existing memory initialization
    ctx.global_memory = GlobalMemoryManager(...)
    ctx.session_manager = SessionManager(...)
    ctx.session_id = ctx.session_manager.prompt_for_session_choice()
    
    # New: Initialize HITL manager
    from src.application.services.agent.deep.session_hitl_manager import SessionHITLManager
    dangerous_tools = {"delete_file", "execute_shell", "rm", "sudo", "chmod", "chown"}
    ctx.hitl_manager = SessionHITLManager(dangerous_tools=dangerous_tools)
```

## 4. Phase 2: Safety Mechanisms

### Step 2.1: Add Timeout Wrapper

**File:** `src/application/services/agent/deep/conversation.py`

**Changes:**
```python
async def handle_deep_agent_query(ctx, query: str) -> str:
    config = _get_agent_config(ctx)
    timeout = config.get("max_execution_time", 120)
    
    try:
        result = await asyncio.wait_for(
            _execute_streaming_query(ctx, query),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        ctx.console.print(f"[red]Timeout after {timeout}s[/]")
        return ""
```

### Step 2.2: Make Recursion Limit Configurable

**File:** `src/components/deepagents/runtime.py`

**Changes:**
```python
def create_deep_agent_runtime(..., model_settings: Dict[str, Any] = None, ...) -> CompiledStateGraph:
    # Read recursion limit from config
    recursion_limit = model_settings.get("max_recursion_limit", 50) if model_settings else 50
    
    # Apply to graph
    return agent_graph.with_config({"recursion_limit": recursion_limit})
```

### Step 2.3: Add User Interrupt Handling

**File:** `src/application/services/agent/deep/conversation.py`

**Changes:**
```python
import signal

async def handle_deep_agent_query(ctx, query: str) -> str:
    interrupted = False
    
    def handle_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True
        ctx.console.print("\n[yellow]Interrupt received...[/]")
    
    original_handler = signal.signal(signal.SIGINT, handle_interrupt)
    
    try:
        async for event in agent.runtime.astream(...):
            if interrupted:
                ctx.console.print("[yellow]Execution interrupted by user[/]")
                return ""
            # Process event...
    finally:
        signal.signal(signal.SIGINT, original_handler)
```

## 5. Phase 3: Memory Integration Fix

### Step 3.1: Fix Checkpointer Initialization

**File:** `src/agents/deepagents/factories/base.py`

**Current issue:**
```python
checkpointer = user_params.get("checkpointer")  # Always None
```

**Fix:**
```python
checkpointer = user_params.get("checkpointer")
if checkpointer is None and global_memory_manager is not None:
    checkpointer_wrapper = create_default_checkpointer()
    checkpointer = checkpointer_wrapper.checkpointer
    logger.info("Created default checkpointer for deep agent")
```

### Step 3.2: Verify Config Usage

**File:** `src/agents/deepagents/instances/base_deep_agent.py`

**Ensure config is built correctly:**
```python
config = {"configurable": {"thread_id": session_id}} if self.enable_memory else None
```

## 6. Phase 4: Token Monitoring (Optional)

### Step 4.1: Create Token Monitor Middleware

**File:** `src/components/deepagents/middlewares/token_monitor.py`

**Implementation:**
```python
class TokenMonitorMiddleware(AgentMiddleware):
    def __init__(self, max_input_tokens=100000, max_output_tokens=50000):
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.input_tokens = 0
        self.output_tokens = 0
    
    def after_model(self, state, runtime):
        # Extract and track token usage
        # Raise TokenLimitExceeded if exceeded
        pass
```

### Step 4.2: Integrate into Runtime

**File:** `src/components/deepagents/runtime.py`

**Add to middleware list:**
```python
if model_settings.get("max_input_tokens"):
    token_monitor = TokenMonitorMiddleware(
        max_input_tokens=model_settings["max_input_tokens"],
        max_output_tokens=model_settings["max_output_tokens"]
    )
    deepagent_middleware.append(token_monitor)
```

## 7. Phase 5: Commands & Polish

### Step 7.1: Add Session Commands

**File:** `src/application/cli/commands/session_commands.py`

**Commands:**
- `/session info` - Show session and HITL preferences
- `/session reset-hitl` - Clear HITL preferences

### Step 7.2: Add Config Commands

**File:** `src/application/cli/commands/config_commands.py`

**Commands:**
- `/config show [category]` - Show configuration
- `/config set <key> <value>` - Temporarily adjust setting
- `/config reset` - Reset to defaults

## 8. Configuration Updates

### Update providers.json

**Add to each model:**
```json
{
  "max_execution_time": 120,
  "max_recursion_limit": 50,
  "max_input_tokens": 100000,
  "max_output_tokens": 50000,
  
  "streaming_enabled": true,
  "stream_mode": "updates",
  "show_reasoning_steps": true,
  "show_tool_calls": true,
  "show_tool_results": true,
  "show_subagent_delegations": true,
  "show_elapsed_time": true,
  
  "hitl_enabled": true,
  "hitl_config": {
    "dangerous_tools": ["delete_file", "execute_shell", "rm", "sudo"],
    "tools": {
      "delete_file": {
        "allow_auto_approve": false,
        "warning_message": "This operation cannot be undone!"
      }
    }
  }
}
```

### Update subagents.json

**Add to each subagent model:**
```json
{
  "max_execution_time": 90,
  "max_recursion_limit": 30,
  "streaming_enabled": false,
  "hitl_enabled": false
}
```

## 9. Testing Checklist

### Unit Tests

- [ ] SessionHITLManager auto-approval logic
- [ ] SessionHITLManager dangerous tools validation
- [ ] HITL handler 4-option processing
- [ ] Event handler progress display
- [ ] Timeout mechanism
- [ ] Interrupt handling

### Integration Tests

- [ ] Full streaming flow from query to response
- [ ] HITL interrupt and resume
- [ ] Memory saving after completion
- [ ] Timeout triggers correctly
- [ ] User interrupt (Ctrl+C) works
- [ ] Token monitoring (if implemented)

### Manual Tests

- [ ] Basic query with no tool calls
- [ ] Query with safe tool calls (auto-approved)
- [ ] Query with dangerous tool (HITL triggered)
- [ ] Option 1: Approve once
- [ ] Option 2: Don't ask again
- [ ] Option 3: Reject
- [ ] Option 4: Tell AI how to do
- [ ] Long-running query (timeout test)
- [ ] Ctrl+C interrupt
- [ ] Session switch (preferences cleared)
- [ ] `/session info` command
- [ ] `/session reset-hitl` command

## 10. Rollback Plan

### If Issues Arise

**Quick rollback:**
1. Revert `base_deep_agent.py` to use `ainvoke`
2. Revert `conversation.py` to original handler
3. Remove new files (event_handler, hitl_handler, etc.)
4. Restore config files from git

**Partial rollback:**
- Keep streaming but disable HITL: `hitl_enabled: false`
- Keep HITL but disable streaming: `streaming_enabled: false`
- Increase limits if too restrictive

### Feature Flags

**Add to config for gradual rollout:**
```json
{
  "experimental_features": {
    "streaming_enabled": true,
    "hitl_enabled": true,
    "token_monitoring_enabled": false
  }
}
```

## 11. Performance Considerations

### Expected Overhead

- **Streaming event processing:** < 5% overhead
- **Console output:** Minimal (async)
- **HITL checks:** Only when tool called
- **Token monitoring:** < 2% overhead

### Optimization Tips

1. **Reduce display verbosity** for faster execution
2. **Cache HITL preferences** in memory (already done)
3. **Batch console updates** if many rapid events
4. **Disable token monitoring** if not needed

## 12. Documentation Updates

### After Implementation

- [ ] Update main README with streaming features
- [ ] Add HITL usage examples
- [ ] Document new commands
- [ ] Update architecture diagrams
- [ ] Add troubleshooting guide
- [ ] Create video demo (optional)

## 13. Success Criteria

### Must Have (P0)

- [ ] Deep Agent uses astream successfully
- [ ] Real-time progress display works
- [ ] HITL 4-option interaction works
- [ ] Session-scoped preferences work
- [ ] Dangerous tools never auto-approve
- [ ] Timeout mechanism works
- [ ] User interrupt (Ctrl+C) works
- [ ] Memory saves after completion
- [ ] Return format matches ainvoke

### Should Have (P1)

- [ ] Token consumption displayed
- [ ] Token limits enforced
- [ ] Session commands work
- [ ] Config commands work

### Nice to Have (P2)

- [ ] Cost estimation displayed
- [ ] Partial result saving
- [ ] Advanced configuration options

