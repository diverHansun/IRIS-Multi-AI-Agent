# Deep Agent Streaming Implementation

Implementation plan for replacing `ainvoke` with `astream` in Deep Agent mode to enable real-time visibility and Human-in-the-Loop interaction.

## 1. Current State Analysis

### Current Implementation

**Deep Agent uses `ainvoke`** (black box execution):
```python
# src/application/services/agent/deep/conversation.py
with ctx.console.status("[dim]Deep agent reasoning...[/]"):
    result = await agent.ainvoke(query, session_id=ctx.session_id)
```

**Problems:**
- No visibility into reasoning steps
- No real-time tool call display
- No human intervention for dangerous operations
- User sees only spinner until completion

### Target Implementation

**Deep Agent will use `astream`** (transparent execution):
```python
# Process streaming events
async for event in agent.runtime.astream(input, config, stream_mode="updates"):
    # Display reasoning steps in real-time
    # Show tool calls as they happen
    # Interrupt for user approval when needed
```

**Benefits:**
- Real-time progress display
- Tool call visibility
- Human-in-the-Loop for dangerous operations
- User can interrupt execution (Ctrl+C)

## 2. Human-in-the-Loop Design

### Two-Layer Security Model

**Layer 1: FilesystemMiddleware (Automatic)**
- Enforces path restrictions (allowed_paths, excluded_paths)
- Blocks oversized files and forbidden extensions
- No user interaction required
- Already implemented

**Layer 2: HITL (Manual Approval)**
- Requires user approval for dangerous tools
- Allows context-based decisions
- Session-scoped preferences
- New implementation

### Four-Option Interaction Model

When a dangerous tool is called, user sees:

```
======================================================================
TOOL EXECUTION REQUIRES APPROVAL
======================================================================

  Tool: delete_file
  Arguments:
    - path: /home/user/old_config.json

  Description: Remove old configuration file

Please choose:
  [1] Yes - Approve this operation
  [2] Yes and don't ask again - Auto-approve in this session
  [3] No - Reject this operation
  [4] Tell AI how to do - Give instructions to AI

Your choice [1-4] (default: 1):
```

**Option Details:**

| Option | Behavior | LangChain Decision | Use Case |
|--------|----------|-------------------|----------|
| **1. Yes** | Approve once | `approve` | Trust this specific operation |
| **2. Don't ask again** | Auto-approve in session | `approve` + save preference | Trust this tool for session |
| **3. No** | Reject | `reject` | Don't execute |
| **4. Tell AI** | Reject with instructions | `reject` + message | Guide AI to better approach |

### Session-Scoped Preferences

**Key Principles:**
- Preferences stored in memory (not persisted to disk)
- Cleared when session ends or switches
- Dangerous tools never allow auto-approval
- User can view/clear preferences with commands

**Implementation:**
```python
class SessionHITLManager:
    def __init__(self, dangerous_tools: Set[str]):
        self.auto_approved_tools: Set[str] = set()
        self.dangerous_tools = dangerous_tools
    
    def can_auto_approve(self, tool_name: str) -> bool:
        return tool_name not in self.dangerous_tools
```

### Dangerous Tools Configuration

**Default dangerous tools:**
- `delete_file` - Cannot be undone
- `execute_shell` - Arbitrary command execution
- `rm`, `sudo`, `chmod`, `chown` - System-level operations

**Configuration in `providers.json`:**
```json
{
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

## 3. Streaming Event Processing

### Event Flow

```
Agent Node Event
    ↓
Display: "Step N | Xs | Processing..."
    ↓
Check for tool calls
    ↓
If tool call → Display tool name and args
    ↓
If subagent → Display delegation
    ↓
Tools Node Event
    ↓
Display: "Result: ..."
    ↓
__interrupt__ Event (HITL)
    ↓
Prompt user for decision
    ↓
Send decision back to agent
    ↓
Resume execution
```

### Progress Display Format

```
Deep agent reasoning...
  Step 1 | 0.5s | Analyzing query...
  Step 2 | 1.2s | Call tool: read_virtual_file
    -> Args: path="config.json"
  Step 3 | 2.1s | Result: File content loaded (1024 bytes)
  Step 4 | 2.8s | Delegate to SubAgent: research
    -> Task: Analyze configuration structure
  Step 5 | 45.3s | SubAgent completed
  Step 6 | 46.1s | Generating response...

DeepAgent > [Final response displayed once]

Summary:
  - Reasoning steps: 6
  - Tool calls: 3 (read_virtual_file, write_virtual_file, search)
  - SubAgent delegations: 1 (research)
  - Total time: 46.1s
```

## 4. Implementation Architecture

### File Modifications

**Core Logic:**
```
src/agents/deepagents/instances/base_deep_agent.py
  └─ invoke() method: replace ainvoke with astream

src/application/services/agent/deep/conversation.py
  └─ handle_deep_agent_query(): process streaming events
```

**New Files:**
```
src/application/services/agent/deep/event_handler.py
  └─ DeepAgentEventHandler class

src/application/services/agent/deep/hitl_handler.py
  └─ handle_hitl_interrupt() function

src/application/services/agent/deep/session_hitl_manager.py
  └─ SessionHITLManager class
```

**Configuration:**
```
config/agents/deep/models/providers.json
  └─ Add streaming_enabled, hitl_config

config/agents/deep/models/subagents.json
  └─ Add streaming_enabled: false for subagents
```

### Return Format Compatibility

**Critical:** `astream` implementation must return same format as `ainvoke`:

```python
{
    "success": True,
    "output": "Final response text",
    "messages": [...],
    "tool_calls": 10,
    "tool_names": ["read_virtual_file", "write_virtual_file"],
    "subagent_calls": [...],
    "session_id": "default"
}
```

### Terminal Integration

**Use `ctx.console` with async wrapper:**
```python
# For output (synchronous, no change needed)
ctx.console.print("[green]Approved[/]")

# For input (wrap with asyncio.to_thread)
choice = await asyncio.to_thread(ctx.console.input, "Your choice: ")
```

**Benefits:**
- Consistent with Basic Agent mode
- Preserves Rich formatting
- No additional dependencies (aioconsole not needed)
- No conflicts between modes

## 5. User Interrupt Handling

### Ctrl+C Interrupt

**Implementation:**
```python
import signal

interrupted = False

def handle_interrupt(signum, frame):
    nonlocal interrupted
    interrupted = True
    ctx.console.print("\n[yellow]Interrupt received, stopping agent...[/]")

signal.signal(signal.SIGINT, handle_interrupt)

async for event in agent.runtime.astream(...):
    if interrupted:
        ctx.console.print("[yellow]Execution interrupted by user[/]")
        return ""
    # Process event...
```

**Behavior:**
- User presses Ctrl+C during execution
- Agent stops gracefully at next event
- Partial results can be saved (optional)
- Interrupt message displayed

## 6. Memory Management

### Global Memory Integration

**Current Issue:**
- `checkpointer=None` passed to `create_deep_agent_runtime`
- `session_id` received but not used in config

**Fix:**
```python
# src/agents/deepagents/factories/base.py
checkpointer = user_params.get("checkpointer")
if checkpointer is None and global_memory_manager is not None:
    checkpointer_wrapper = create_default_checkpointer()
    checkpointer = checkpointer_wrapper.checkpointer
```

**Save Strategy:**
- LangGraph checkpointer: auto-saves after each node (already working)
- Global memory: save once after query completes

```python
# After streaming completes
if ctx.global_memory:
    ctx.global_memory.add_conversation(
        session_id=ctx.session_id,
        user_message=query,
        ai_response=final_output
    )
```

## 7. Session Commands

### HITL Management Commands

**View preferences:**
```bash
/session info
```

**Clear preferences:**
```bash
/session reset-hitl
```

**Output example:**
```
Current Session Information:
  Session ID: default

HITL Preferences (this session only):
  Auto-approved tools:
    - write_virtual_file
    - read_virtual_file

  Dangerous tools (never auto-approve):
    - delete_file
    - execute_shell
```

## 8. Complete Interaction Example

```
> Create a backup of my config and delete the old one

Deep agent reasoning...
  Step 1 | 0.8s | Planning backup operation...
  Step 2 | 1.5s | Call tool: write_virtual_file

======================================================================
TOOL EXECUTION REQUIRES APPROVAL
======================================================================

  Tool: write_virtual_file
  Arguments:
    - path: /home/user/config.backup.json
    - content: {...}

Please choose:
  [1] Yes - Approve this operation
  [2] Yes and don't ask again - Auto-approve in this session
  [3] No - Reject this operation
  [4] Tell AI how to do - Give instructions to AI

Your choice [1-4] (default: 1): 2

Approved and will auto-approve 'write_virtual_file' in this session

  Step 3 | 2.2s | Backup created successfully
  Step 4 | 2.8s | Call tool: delete_file

======================================================================
TOOL EXECUTION REQUIRES APPROVAL
======================================================================
WARNING: This is a potentially dangerous operation!
This operation cannot be undone!
======================================================================

  Tool: delete_file
  Arguments:
    - path: /home/user/old_config.json

Please choose:
  [1] Yes - Approve this operation
  [2] (Not available for dangerous operations)
  [3] No - Reject this operation
  [4] Tell AI how to do - Give instructions to AI

Your choice [1,3,4]: 4

Your instructions: Don't delete it, just move it to archive folder

Instructions sent to AI

  Step 5 | 15.3s | Reconsidering approach...
  Step 6 | 16.0s | Call tool: move_file

Auto-approved: move_file (session preference)

  Step 7 | 16.5s | File moved to archive

DeepAgent > I've created a backup at config.backup.json and moved the old config to the archive folder instead of deleting it.
```

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Session-scoped preferences | Security: prevents permanent auto-approval of dangerous operations |
| 4-option model | UX: covers all user needs (approve, remember, reject, guide) |
| Tell AI unlimited retries | Flexibility: AI should keep trying until user is satisfied |
| Dangerous tools list | Safety: certain operations always require explicit approval |
| ctx.console for terminal | Consistency: same terminal API across all modes |
| Save memory after completion | Performance: avoid frequent disk I/O during execution |
| Process streaming, result once | UX: show progress but keep final answer clean |
