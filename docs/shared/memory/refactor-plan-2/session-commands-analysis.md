# Session Commands and Mode Switching Analysis

## Question 1: Will session commands work after refactoring?

**Answer: Yes, all session commands remain functional.**

After separating LLM/Basic Agent/Deep Agent into isolated storage directories, session commands continue to work with the following behavior:

### Commands and Their Behavior

| Command | Functionality | Notes |
|---------|---------------|-------|
| `/new` | Creates new session in current mode's directory | Works normally |
| `/sessions` | Lists sessions from current mode or all modes grouped | Enhanced with cross-mode view option |
| `/restore` | Restores session from current mode | Shows helpful error if session in different mode |
| `/clear` | Clears current session | No change |
| `/cleanup` | Cleans orphaned sessions in current mode | No change |
| `/delete_session` | Deletes session from current mode | No change |

### Key Design Points

**1. Mode-specific storage**

Each mode has its own storage directory:
```
data/
├── llm/sessions/           # LLM mode sessions
├── basicagent/sessions/    # Basic Agent sessions
└── deepagent/sessions/     # Deep Agent sessions
```

**2. Commands operate on current mode**

When you use `/sessions` in Basic Agent mode, it shows Basic Agent sessions. When in LLM mode, it shows LLM sessions.

**3. Cross-mode session handling**

If user tries to `/restore` a session that exists in a different mode:

```
[Basic Agent] User: /restore user_20240101_deep123

System: Session 'user_20240101_deep123' exists in 'deep' mode, not current mode 'basic'.
        Switch to deep mode first using /mode deep.
```

**4. Optional grouped view for `/sessions`**

Implementation can choose to show all modes:

```
User: /sessions

LLM Mode (2 sessions):
  user_20240101_abc123 (5 messages)
  user_20240102_xyz789 (3 messages)

Basic Agent (1 session):
  user_20240101_def456 (10 messages) <- current

Deep Agent (0 sessions)
```

---

## Question 2: How should sessions change when switching modes?

**Answer: Automatically load most recent session from target mode, or create new one.**

### Mode Switching Behavior

When using `/switch` or `/mode` to change modes:

**Step 1: Create mode-specific memory manager**
```python
if new_mode == "llm":
    ctx.session_manager = SessionManager(mode="llm")
    ctx.llm_memory = LLMMemory(storage_dir="data/llm/sessions")
elif new_mode == "basic":
    ctx.session_manager = SessionManager(mode="basic")
    ctx.basic_checkpointer = BasicAgentCheckpointer(storage_dir="data/basicagent/sessions")
elif new_mode == "deep":
    ctx.session_manager = SessionManager(mode="deep")
    ctx.deep_checkpointer = DeepAgentCheckpointer(storage_dir="data/deepagent/sessions")
```

**Step 2: Load most recent session from target mode**
```python
recent_session = ctx.session_manager.get_most_recent_session()
if recent_session:
    ctx.session_id = recent_session["session_id"]
    ctx.console.print(f"[dim]Loaded {new_mode} session: {ctx.session_id}[/]")
else:
    # No existing session, create new one
    ctx.session_id = ctx.session_manager.create_new_session()
    ctx.console.print(f"[dim]Created new {new_mode} session: {ctx.session_id}[/]")
```

### Example Workflow

```
User: /switch llm
System: Loaded LLM session: user_20240101_abc123

User: (chats in LLM mode...)

User: /mode deep
System: Created new deep mode session: user_20240101_ghi789

User: (chats in deep mode...)

User: /mode basic
System: Loaded basic agent session: user_20240101_def456

User: /sessions
System:
  LLM Mode:
    user_20240101_abc123 (8 messages)
  Basic Agent:
    user_20240101_def456 (12 messages) <- current
  Deep Agent:
    user_20240101_ghi789 (4 messages)
```

### Design Rationale

**Why automatic session switch?**

1. **Mode-specific contexts**
   - LLM mode conversations may not make sense for Deep Agent
   - Basic Agent tool calls may not be relevant in LLM mode
   - Each mode has different capabilities and conversation styles

2. **Clear separation prevents confusion**
   - Users understand each mode has its own conversation history
   - No mixed contexts (e.g., LLM conversation suddenly seeing agent tool calls)

3. **Predictable behavior**
   - Always loads most recent session from target mode
   - If no session exists, creates new one
   - Session ID changes when switching modes (expected behavior)

### Alternative Design (Not Recommended)

**Option: Keep same session ID across modes**

```python
# When switching modes, try to use current session_id
if ctx.session_manager.session_exists(ctx.session_id, mode=new_mode):
    # Session exists in new mode, keep it
    pass
else:
    # Session doesn't exist, load most recent or create new
    ...
```

**Why not recommended:**
- Same session_id in different modes would contain different conversations
- Confusing when user restores a session and sees different content than expected
- Violates principle of mode isolation

---

## Implementation Updates

### SessionManager Constructor Change

**Before**:
```python
SessionManager(memory_manager: GlobalMemoryManager, mode: str = "basic")
```

**After**:
```python
SessionManager(mode: str = "basic")
```

No longer depends on `GlobalMemoryManager`. Directly accesses `SessionStorage` for each mode.

### New SessionManager Methods

```python
def list_sessions(self, mode: Optional[str] = None) -> List[Dict]:
    """List sessions from specified mode (defaults to current mode)"""
    target_mode = mode or self.mode
    storage = SessionStorage(self.storage_dirs[target_mode])
    return storage.list_sessions()

def list_all_sessions(self) -> Dict[str, List[Dict]]:
    """List sessions from all modes, grouped by mode"""
    return {
        mode: SessionStorage(dir).list_sessions()
        for mode, dir in self.storage_dirs.items()
    }

def session_exists(self, session_id: str, mode: Optional[str] = None) -> bool:
    """Check if session exists in specified mode"""
    target_mode = mode or self.mode
    storage = SessionStorage(self.storage_dirs[target_mode])
    return storage.session_exists(session_id)
```

### Command Updates

**File**: `src/application/commands/shared/session_commands.py`

**`/sessions` command**:
```python
async def execute(self, ctx, args: str) -> CommandResult:
    # Option 1: Show all modes grouped (recommended)
    all_sessions = ctx.session_manager.list_all_sessions()
    return CommandResult(
        type="render",
        payload={
            "kind": "sessions_grouped",
            "sessions": all_sessions,
            "current_mode": ctx.session_manager.mode,
            "current_session_id": ctx.session_id,
        },
    )
```

**`/restore` command**:
```python
async def execute(self, ctx, args: str) -> CommandResult:
    target = args.strip()

    # Check if session exists in current mode
    if not ctx.session_manager.session_exists(target):
        # Try to find in other modes
        found_in_mode = None
        for mode in ["llm", "basic", "deep"]:
            if ctx.session_manager.session_exists(target, mode=mode):
                found_in_mode = mode
                break

        if found_in_mode:
            return CommandResult.error(
                f"Session '{target}' exists in '{found_in_mode}' mode, not current mode. "
                f"Switch to {found_in_mode} mode first."
            )
        else:
            return CommandResult.error(f"Session does not exist: {target}")

    # Session exists in current mode, restore it
    ctx.session_id = target
    return CommandResult.success(f"Switched to session: {target}")
```

---

## Summary

**Question 1: Will session commands work?**
- Yes, all commands remain functional
- Commands operate on current mode's storage
- Enhanced with cross-mode awareness (helpful error messages)

**Question 2: How should sessions change when switching modes?**
- Automatically load most recent session from target mode
- If no session exists, create new one
- Session ID changes when switching modes (by design)
- This ensures clear separation between mode-specific conversations

**Benefits of this design:**
- Clear mode isolation prevents confusion
- Predictable behavior (always loads most recent from target mode)
- Helpful error messages guide users to correct mode
- Optional grouped view shows sessions across all modes
