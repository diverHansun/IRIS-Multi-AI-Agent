# Integration Guide

## Overview

This document describes how to integrate the new memory architecture with existing LLM and Agent services.

---

## LLM Mode Integration

### Current Implementation

**File**: `src/application/services/llm/conversation.py`

**Before**:
```python
from src.components.shared.memory import GlobalMemoryManager

async def handle_llm_query(ctx, llm, provider, query, streaming=True):
    # Execute LLM
    response = await llm.ainvoke([HumanMessage(content=query)])
    answer = response.content

    # Save conversation
    if ctx.global_memory:
        ctx.global_memory.add_llm_conversation(ctx.session_id, query, answer)

    return answer
```

### New Implementation

**After**:
```python
from src.components.shared.memory import LLMMemory

async def handle_llm_query(ctx, llm, provider, query, streaming=True):
    # Execute LLM
    response = await llm.ainvoke([HumanMessage(content=query)])
    answer = response.content

    # Save conversation
    if ctx.llm_memory:
        ctx.llm_memory.add_conversation(ctx.session_id, query, answer)

    return answer
```

### Initialization

**File**: `src/application/cli/main.py` or service initialization

**Before**:
```python
ctx.global_memory = GlobalMemoryManager(agent_mode="llm", max_messages=50)
```

**After**:
```python
ctx.llm_memory = LLMMemory(storage_dir="data/llm/sessions")
```

### History Access (Optional)

If LLM service needs to access history (for context window):

```python
# Get recent history
history = ctx.llm_memory.get_history(ctx.session_id, max_messages=10)

# Construct prompt with history
messages = history + [HumanMessage(content=query)]
response = await llm.ainvoke(messages)
```

---

## Basic Agent Integration

### Current Implementation

**File**: `src/application/services/agent/basic/conversation.py`

**Before**:
```python
from src.components.shared.memory import MemorySyncAdapter, SessionContext

async def handle_agent_query(ctx, query: str) -> str:
    # Get agent
    agent = ctx.agent_instance

    # Execute
    result = await agent.ainvoke(query, session_id=ctx.session_id)

    # Persist (BUGGY - overwrites history)
    session_ctx = SessionContext(
        session_id=ctx.session_id,
        agent_type="basic",
        provider=ctx.provider,
    )
    ctx.memory_sync.persist_from_runtime(
        session_ctx,
        agent.checkpointer,
        None,
        result,
    )

    return result.get("output", "")
```

### New Implementation

**After**:
```python
# No manual persistence needed!

async def handle_agent_query(ctx, query: str) -> str:
    # Get agent
    agent = ctx.agent_instance

    # Execute (checkpointer handles persistence automatically)
    result = await agent.ainvoke(query, session_id=ctx.session_id)

    return result.get("output", "")
```

### Agent Creation

**File**: `src/agents/basicagents/adapters/base_adapter.py`

**Before**:
```python
from langgraph.checkpoint.memory import MemorySaver

async def create_agent(self, provider, model, tools, config):
    # Create checkpointer (in-memory)
    checkpointer = MemorySaver() if config.agent_params["memory_enabled"] else None

    # Create agent with checkpointer
    agent = await self._build_agent(llm, tools, checkpointer, config)

    return agent
```

**After**:
```python
from src.components.shared.memory import BasicAgentCheckpointer

async def create_agent(self, provider, model, tools, config):
    # Create checkpointer (persistent)
    checkpointer = BasicAgentCheckpointer(
        storage_dir="data/basicagent/sessions"
    ) if config.agent_params["memory_enabled"] else None

    # Create agent with checkpointer
    agent = await self._build_agent(llm, tools, checkpointer, config)

    return agent
```

### Key Changes

1. **Replace MemorySaver with BasicAgentCheckpointer**
   - Old: `MemorySaver()` (in-memory, problematic)
   - New: `BasicAgentCheckpointer()` (persistent, correct)

2. **Remove manual persistence**
   - Old: Call `memory_sync.persist_from_runtime()` after execution
   - New: LangGraph calls `checkpointer.put()` automatically

3. **No need for MemorySyncAdapter**
   - Old: `ctx.memory_sync = MemorySyncAdapter(...)`
   - New: Not needed (checkpointer is self-contained)

---

## Deep Agent Integration

### Current Implementation

**File**: `src/application/services/agent/deep/streaming/conversation.py`

**Before**:
```python
from src.components.shared.memory import MemorySyncAdapter, SessionContext, GlobalMemoryManager
from src.components.shared.persistence import persist_conversation_state

async def handle_deep_agent_query(ctx, query: str):
    # Setup
    session_ctx = SessionContext(
        session_id=ctx.session_id,
        agent_type="deep",
        provider=ctx.provider,
        function_type="research",
    )

    # Load history
    input_data = ctx.memory_sync.enhance_runtime_input(
        session_ctx,
        query,
        max_history=10
    )

    # Execute (streaming)
    async for event in agent.runtime.astream(input_data, config):
        # ... handle events ...

    # Persist
    ctx.memory_sync.persist_from_runtime(
        session_ctx,
        agent.runtime_checkpointer,
        runtime_config,
        final_state,
    )

    # On error/timeout
    await persist_conversation_state(
        session_ctx,
        agent.runtime_checkpointer,
        runtime_config,
        ctx.memory_sync,
        reason="timeout",
    )
```

### New Implementation

**After**:
```python
from src.components.shared.memory import DeepAgentCheckpointer

async def handle_deep_agent_query(ctx, query: str):
    # Setup (simplified, no SessionContext needed)
    deep_checkpointer = ctx.deep_checkpointer

    # Load history
    input_data = deep_checkpointer.enhance_runtime_input(
        ctx.session_id,
        query,
        max_history=10
    )

    # Execute (streaming)
    async for event in agent.runtime.astream(input_data, config):
        # ... handle events ...

    # Persist
    deep_checkpointer.persist_from_runtime(
        ctx.session_id,
        agent.runtime_checkpointer,
        runtime_config,
        final_state,
    )

    # On error/timeout (simpler)
    deep_checkpointer.persist_from_runtime(
        ctx.session_id,
        agent.runtime_checkpointer,
        runtime_config,
        final_state,
    )
```

### Initialization

**File**: `src/application/cli/main.py` or engine switch command

**Before**:
```python
ctx.global_memory = GlobalMemoryManager(agent_mode="deep", max_messages=50)
ctx.memory_sync = MemorySyncAdapter(ctx.global_memory, agent_mode="deep")
```

**After**:
```python
ctx.deep_checkpointer = DeepAgentCheckpointer(storage_dir="data/deepagent/sessions")
```

### Key Changes

1. **Replace MemorySyncAdapter with DeepAgentCheckpointer**
   - Old: `MemorySyncAdapter(global_memory, agent_mode="deep")`
   - New: `DeepAgentCheckpointer()`

2. **Remove GlobalMemoryManager dependency**
   - Old: Need `global_memory` for Deep Agent
   - New: Checkpointer is self-contained

3. **Simplify API**
   - Old: `enhance_runtime_input(session_ctx, ...)`
   - New: `enhance_runtime_input(session_id, ...)`

4. **Remove SessionContext (optional)**
   - Deep Agent can work directly with `session_id`
   - `SessionContext` still available if needed for namespace isolation

---

## Session Management Integration

### Current Implementation

**File**: `src/application/commands/shared/session_commands.py`

**Before**:
```python
from src.components.shared.memory import GlobalMemoryManager, SessionManager

# /sessions command
def list_sessions_command(ctx):
    sessions = ctx.global_memory.list_sessions()
    # Display sessions

# /restore command
def restore_session_command(ctx, session_id):
    if ctx.global_memory.session_exists(session_id):
        ctx.session_id = session_id
        # Success
```

### New Implementation

**After**:
```python
from src.components.shared.memory import SessionManager

# /sessions command
def list_sessions_command(ctx):
    # List current mode sessions
    sessions = ctx.session_manager.list_sessions()

    # OR list all modes
    all_sessions = ctx.session_manager.list_all_sessions()
    # Display grouped by mode

# /restore command
def restore_session_command(ctx, session_id: str, mode: str = None):
    if ctx.session_manager.session_exists(session_id, mode):
        ctx.session_id = session_id
        if mode and mode != ctx.session_manager.mode:
            # Cross-mode restore (optional)
            ctx.session_manager.mode = mode
        # Success
```

### Initialization

**File**: `src/application/cli/main.py`

**Before**:
```python
ctx.global_memory = GlobalMemoryManager(agent_mode="basic", max_messages=50)
ctx.session_manager = SessionManager(ctx.global_memory, mode="basic")
```

**After**:
```python
ctx.session_manager = SessionManager(mode="basic")
```

### Enhanced Features

**List all sessions grouped by mode**:
```python
# /sessions command output
all_sessions = ctx.session_manager.list_all_sessions()

# Display:
# LLM Mode:
#   * session_1 (4 messages)
# Basic Agent:
#   * session_2 (8 messages)
# Deep Agent:
#   * session_3 (12 messages)
```

---

## Engine Switch Integration

### Current Implementation

**File**: `src/application/commands/engine_commands.py`

**Before**:
```python
from src.components.shared.memory import GlobalMemoryManager, SessionManager, MemorySyncAdapter

def switch_engine(ctx, new_mode: str):
    # Switch to LLM
    if new_mode == "llm":
        ctx.global_memory = GlobalMemoryManager(agent_mode="llm", max_messages=50)
        ctx.session_manager = SessionManager(ctx.global_memory, mode="llm")

    # Switch to Basic Agent
    elif new_mode == "basic":
        ctx.global_memory = GlobalMemoryManager(agent_mode="basic", max_messages=50)
        ctx.session_manager = SessionManager(ctx.global_memory, mode="basic")
        ctx.memory_sync = MemorySyncAdapter(ctx.global_memory, agent_mode="basic")

    # Switch to Deep Agent
    elif new_mode == "deep":
        ctx.global_memory = GlobalMemoryManager(agent_mode="deep", max_messages=50)
        ctx.session_manager = SessionManager(ctx.global_memory, mode="deep")
        ctx.memory_sync = MemorySyncAdapter(ctx.global_memory, agent_mode="deep")

    # Load most recent session (BUG: overwrites user's /restore selection)
    recent_session = ctx.session_manager.get_most_recent_session()
    if recent_session:
        ctx.session_id = recent_session["session_id"]
```

### New Implementation

**After**:
```python
from src.components.shared.memory import (
    LLMMemory,
    BasicAgentCheckpointer,
    DeepAgentCheckpointer,
    SessionManager,
)

def switch_engine(ctx, new_mode: str):
    # Update session manager mode
    ctx.session_manager.mode = new_mode

    # Switch to LLM
    if new_mode == "llm":
        ctx.llm_memory = LLMMemory(storage_dir="data/llm/sessions")
        # Clean up other mode objects
        ctx.basic_checkpointer = None
        ctx.deep_checkpointer = None

    # Switch to Basic Agent
    elif new_mode == "basic":
        ctx.basic_checkpointer = BasicAgentCheckpointer(storage_dir="data/basicagent/sessions")
        # Clean up other mode objects
        ctx.llm_memory = None
        ctx.deep_checkpointer = None

    # Switch to Deep Agent
    elif new_mode == "deep":
        ctx.deep_checkpointer = DeepAgentCheckpointer(storage_dir="data/deepagent/sessions")
        # Clean up other mode objects
        ctx.llm_memory = None
        ctx.basic_checkpointer = None

    # Preserve user-selected session (FIX: don't overwrite /restore)
    if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode=new_mode):
        # Keep user's selection
        pass
    else:
        # Load most recent session in new mode
        recent_session = ctx.session_manager.get_most_recent_session(mode=new_mode)
        if recent_session:
            ctx.session_id = recent_session["session_id"]
        else:
            # Create new session
            ctx.session_id = ctx.session_manager.create_new_session()
```

### Key Fixes

1. **Preserve user's /restore selection**
   - Old: Always load most recent session (overwrites user choice)
   - New: Only load recent if no valid session selected

2. **Mode-specific memory objects**
   - Old: Single `global_memory` for all modes
   - New: Separate objects per mode

3. **Clean separation**
   - Old: `memory_sync` used by both Basic and Deep (confusing)
   - New: Each mode has its own object

---

## CLI Context Updates

### Before

```python
class CLIContext:
    global_memory: GlobalMemoryManager
    session_manager: SessionManager
    memory_sync: MemorySyncAdapter  # Used by Basic and Deep
    session_id: str
```

### After

```python
class CLIContext:
    # Session management (shared)
    session_manager: SessionManager
    session_id: str

    # Mode-specific memory objects
    llm_memory: Optional[LLMMemory] = None
    basic_checkpointer: Optional[BasicAgentCheckpointer] = None
    deep_checkpointer: Optional[DeepAgentCheckpointer] = None

    # Current mode
    current_mode: str  # "llm", "basic", or "deep"
```

**Initialization**:
```python
# At startup (default: Basic Agent)
ctx.session_manager = SessionManager(mode="basic")
ctx.basic_checkpointer = BasicAgentCheckpointer()
ctx.session_id = ctx.session_manager.create_new_session()
ctx.current_mode = "basic"
```

---

## Migration Checklist

### Phase 1: Preparation
- [ ] Create new files: `llm_memory.py`, `basic_agent_checkpointer.py`, `deep_agent_checkpointer.py`
- [ ] Enhance `session_manager.py` with cross-mode support
- [ ] Update imports in `src/components/shared/memory/__init__.py`

### Phase 2: LLM Mode
- [ ] Update `src/application/services/llm/conversation.py`
- [ ] Replace `global_memory.add_llm_conversation()` with `llm_memory.add_conversation()`
- [ ] Update CLI initialization
- [ ] Test LLM mode

### Phase 3: Basic Agent Mode
- [ ] Update `src/agents/basicagents/adapters/base_adapter.py`
- [ ] Replace `MemorySaver` with `BasicAgentCheckpointer`
- [ ] Update `src/application/services/agent/basic/conversation.py`
- [ ] Remove `persist_from_runtime()` calls
- [ ] Test Basic Agent mode

### Phase 4: Deep Agent Mode
- [ ] Update `src/application/services/agent/deep/streaming/conversation.py`
- [ ] Replace `MemorySyncAdapter` with `DeepAgentCheckpointer`
- [ ] Remove `persist_conversation_state()` calls
- [ ] Test Deep Agent mode (verify HITL still works)

### Phase 5: Commands
- [ ] Update `/sessions` command to show grouped sessions
- [ ] Update `/restore` command to support cross-mode restore
- [ ] Update `/switch` command to preserve user selection
- [ ] Test all commands

### Phase 6: Cleanup
- [ ] Delete `global_memory.py`
- [ ] Delete `memory_sync.py`
- [ ] Delete `config.py`
- [ ] Delete `persistence/helpers.py`
- [ ] Update documentation

---

## Testing

### LLM Mode
```
1. /switch llm
2. Ask question
3. Check data/llm/sessions/*.json (should have 2 messages)
4. Ask another question
5. Check file (should have 4 messages, not overwritten)
```

### Basic Agent Mode
```
1. /switch agent
2. Ask question requiring tools
3. Check data/basicagent/sessions/*.json
4. /restore <session_id>
5. /switch llm
6. /switch agent
7. Ask question (should load history automatically)
```

### Deep Agent Mode
```
1. /switch deep
2. Ask complex question
3. Trigger HITL approval
4. Approve and continue
5. Check data/deepagent/sessions/*.json
6. Verify state recovery works
```

### Cross-Mode
```
1. /switch llm
2. Chat for 3 turns
3. /sessions (should show LLM sessions)
4. /switch agent
5. /sessions (should show both LLM and Basic sessions)
6. /restore <llm_session_id> (cross-mode restore)
```

---

## Summary

The integration is straightforward because the new architecture is **cleaner and simpler**:

**Old**: Shared objects with mixed responsibilities
- `GlobalMemoryManager` serves all modes
- `MemorySyncAdapter` serves Basic and Deep
- Manual persistence calls

**New**: Mode-specific objects with clear responsibilities
- `LLMMemory` for LLM mode
- `BasicAgentCheckpointer` for Basic mode
- `DeepAgentCheckpointer` for Deep mode
- Automatic persistence (LangGraph handles it)

Most changes are **deletions** (removing manual persistence) or **simple replacements** (swapping class names).

---

## Session Commands Behavior After Refactoring

### Session Command Compatibility

All session commands (`/new`, `/sessions`, `/restore`, `/cleanup`, `/delete_session`, `/clear`) remain functional after refactoring. Key points:

**1. Commands operate on current mode's storage**

Each mode has its own storage directory:
```
data/llm/sessions/           # /sessions in LLM mode shows these
data/basicagent/sessions/    # /sessions in Basic Agent mode shows these
data/deepagent/sessions/     # /sessions in Deep Agent mode shows these
```

**2. `/sessions` command options**

Option A (Recommended): Show all modes grouped
```python
# In session_commands.py
sessions = ctx.session_manager.list_all_sessions()

# Output:
# LLM Mode (2 sessions):
#   user_20240101_abc123 (5 messages)
#   user_20240102_xyz789 (3 messages)
# Basic Agent (1 session):
#   user_20240101_def456 (10 messages) <- current
# Deep Agent (0 sessions)
```

Option B: Show current mode only
```python
sessions = ctx.session_manager.list_sessions()  # Current mode only
```

**3. `/restore` cross-mode handling**

When restoring a session that exists in a different mode:

```python
# In session_commands.py
if not ctx.session_manager.session_exists(target):
    # Check other modes
    for mode in ["llm", "basic", "deep"]:
        if ctx.session_manager.session_exists(target, mode=mode):
            return CommandResult.error(
                f"Session '{target}' exists in '{mode}' mode, not current mode. "
                f"Switch to {mode} mode first."
            )
```

User experience:
```
[Basic Agent] User: /restore user_20240101_ghi789
System: Session 'user_20240101_ghi789' exists in 'deep' mode, not current mode.
        Switch to deep mode first using /mode deep.
```

**4. Other commands require no changes**

- `/new` - Creates session in current mode's directory
- `/clear` - Clears current mode's session
- `/cleanup` - Cleans orphaned sessions in current mode
- `/delete_session` - Deletes from current mode (shows error if not found)

---

## Mode Switching Behavior

### Session Handling During Mode Switch

When switching modes (`/switch` or `/mode`), the system automatically:

1. Loads most recent session from target mode
2. If no session exists, creates new one
3. Preserves session isolation (no cross-mode sharing)

**Example workflow**:

```
User: /switch llm
System: Loaded LLM session: user_20240101_abc123

User: chat for a while...

User: /mode deep
System: Created new deep mode session: user_20240101_ghi789

User: chat in deep mode...

User: /mode basic
System: Loaded basic agent session: user_20240101_def456

User: /sessions
System:
  LLM Mode (1 session):
    user_20240101_abc123 (8 messages)
  Basic Agent (1 session):
    user_20240101_def456 (12 messages) <- current
  Deep Agent (1 session):
    user_20240101_ghi789 (4 messages)
```

### Implementation Details

**File**: `src/application/commands/engine_commands.py`

```python
async def execute(self, ctx, args: str) -> CommandResult:
    # ... parse engine ...

    if engine == "llm":
        ctx.session_manager = SessionManager(mode="llm")
        ctx.llm_memory = LLMMemory()

        # Load most recent or create new
        recent = ctx.session_manager.get_most_recent_session()
        if recent:
            ctx.session_id = recent["session_id"]
            ctx.console.print(f"[dim]Loaded LLM session: {ctx.session_id}[/]")
        else:
            ctx.session_id = ctx.session_manager.create_new_session()
            ctx.console.print(f"[dim]Created new LLM session: {ctx.session_id}[/]")

    elif engine == "agent":
        agent_type = ctx.get_engine_config("agent").get("agent_type", "basic")

        if agent_type == "basic":
            ctx.session_manager = SessionManager(mode="basic")
            ctx.basic_checkpointer = BasicAgentCheckpointer()

            recent = ctx.session_manager.get_most_recent_session()
            if recent:
                ctx.session_id = recent["session_id"]
                ctx.console.print(f"[dim]Loaded basic session: {ctx.session_id}[/]")
            else:
                ctx.session_id = ctx.session_manager.create_new_session()
                ctx.console.print(f"[dim]Created new basic session: {ctx.session_id}[/]")

        elif agent_type == "deep":
            ctx.session_manager = SessionManager(mode="deep")
            ctx.deep_checkpointer = DeepAgentCheckpointer()

            recent = ctx.session_manager.get_most_recent_session()
            if recent:
                ctx.session_id = recent["session_id"]
                ctx.console.print(f"[dim]Loaded deep session: {ctx.session_id}[/]")
            else:
                ctx.session_id = ctx.session_manager.create_new_session()
                ctx.console.print(f"[dim]Created new deep session: {ctx.session_id}[/]")
```

**File**: `src/application/commands/agent/mode_commands.py`

Same pattern for `/mode basic` and `/mode deep` commands.

### Session Continuity vs Isolation

**Design Decision**: Prioritize isolation over continuity

**Rationale**:
- LLM, Basic Agent, and Deep Agent have different capabilities
- Conversations in one mode may not make sense in another
- Clear separation prevents confusion

**Alternative** (optional future enhancement):
Add `--copy-history` flag to copy session from one mode to another:
```
User: /mode deep --copy-history
System: Created deep session user_20240101_new123
        Copied 8 messages from basic session user_20240101_def456
```

---

## SessionManager API Updates

### Constructor Change

**Before**:
```python
SessionManager(memory_manager: GlobalMemoryManager, mode: str = "basic")
```

**After**:
```python
SessionManager(mode: str = "basic")
```

### New Methods

```python
# List sessions from specific mode
def list_sessions(self, mode: Optional[str] = None) -> List[Dict]:
    """List sessions from specified mode (defaults to current mode)"""

# List sessions from all modes
def list_all_sessions(self) -> Dict[str, List[Dict]]:
    """Returns: {"llm": [...], "basic": [...], "deep": [...]}"""

# Check existence in specific mode
def session_exists(self, session_id: str, mode: Optional[str] = None) -> bool:
    """Check if session exists in specified mode (defaults to current mode)"""
```

### Updated Methods

All methods that previously called `self.memory_manager.xxx()` now call `SessionStorage` directly:

```python
@property
def storage(self):
    return SessionStorage(self.storage_dirs[self.mode])

def create_new_session(self) -> str:
    session_id = f"user_{timestamp}_{uuid}"
    self.storage.initialize_empty_session(session_id)  # Changed
    return session_id

def get_most_recent_session(self) -> Optional[Dict]:
    sessions = self.storage.list_sessions()  # Changed
    return sessions[0] if sessions else None
```

---

## Summary of Command Behavior Changes

| Command | Before | After |
|---------|--------|-------|
| `/new` | Creates in shared directory | Creates in mode-specific directory |
| `/sessions` | Shows shared sessions | Shows current mode or all modes grouped |
| `/restore` | Restores if exists | Validates mode, shows helpful error if cross-mode |
| `/clear` | Clears current session | Same (no change) |
| `/cleanup` | Cleans shared directory | Cleans current mode's directory |
| `/delete_session` | Deletes from shared | Deletes from current mode |
| `/switch` | Overwrites `/restore` selection | Loads most recent from target mode |
| `/mode` | Overwrites session | Loads most recent from target mode |

All commands remain functional. Main improvements:
- Clearer mode isolation
- Better error messages for cross-mode operations
- Optional grouped view for `/sessions` command
