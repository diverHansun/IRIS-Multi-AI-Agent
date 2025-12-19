# Memory Module Architecture Refactoring

## Overview

This document describes the refactoring of the memory module from a shared, mixed-responsibility architecture to a modular, mode-specific architecture.

---

## Old Architecture

### Directory Structure (Before)

```
src/components/shared/
├── memory/
│   ├── __init__.py
│   ├── global_memory.py              # Mixed: LLM + Deep + SessionManager logic
│   ├── session_manager.py            # Session lifecycle management
│   ├── session_context.py            # Deep Agent specific
│   ├── memory_sync.py                # Deep Agent + Basic Agent sync
│   ├── config.py                     # Storage path configuration
│   └── unified_checkpointer.py       # Deprecated
├── storage/
│   ├── session_storage.py            # File I/O operations
│   └── message_filter.py             # Message filtering logic
└── persistence/
    └── helpers.py                    # Deep Agent persistence utilities
```

### Module Responsibilities (Before)

#### `global_memory.py` - Mixed Responsibilities

**Problems**:
- Serves both LLM mode and Deep mode
- Contains session management logic (should be in SessionManager)
- Tightly coupled with multiple modes

**Key Classes**:
```python
class GlobalMemoryManager:
    # LLM mode operations
    def add_llm_conversation(session_id, user_msg, ai_msg)

    # Session management (should be in SessionManager)
    def list_sessions()
    def session_exists(session_id)
    def get_session_info(session_id)

    # Storage management
    def get_session_history(session_id)
    def save_session(session_id, messages)
```

#### `memory_sync.py` - Deep Agent + Basic Agent

**Problems**:
- Serves both Deep Agent and Basic Agent
- Basic Agent's `persist_from_runtime()` has overwrite bug

**Key Functions**:
```python
class MemorySyncAdapter:
    def enhance_runtime_input()      # Deep Agent only
    def persist_from_runtime()       # Deep Agent + Basic Agent (problematic)
```

#### `config.py` - Storage Path Configuration

**Contents**:
```python
BASIC_LLM_STORAGE_DIR = "data/llm_basicagent/sessions"
DEEP_STORAGE_DIR = "data/deepagent/sessions"

AGENT_MODE_STORAGE_MAP = {
    "basic": BASIC_LLM_STORAGE_DIR,
    "llm": BASIC_LLM_STORAGE_DIR,
    "deep": DEEP_STORAGE_DIR,
}
```

**Problem**: Basic and LLM share the same directory, causing conflicts.

### Data Flow (Before)

```
LLM Mode:
  LLM Service → GlobalMemoryManager.add_llm_conversation()
              → SessionStorage(data/llm_basicagent/)

Basic Agent Mode:
  BasicAgent → MemorySaver (in-memory)
             → persist_from_runtime() - OVERWRITE BUG
             → SessionStorage(data/llm_basicagent/)

Deep Agent Mode:
  DeepAgent → MemorySaver (runtime)
            → MemorySyncAdapter.persist_from_runtime()
            → GlobalMemoryManager
            → SessionStorage(data/deepagent/)
```

### Key Issues

1. **Shared Directory Conflict**: Basic and LLM modes share `data/llm_basicagent/`, causing session ID conflicts
2. **Overwrite Bug**: Basic Agent's `persist_from_runtime()` overwrites existing history
3. **Mixed Responsibilities**: `GlobalMemoryManager` serves multiple modes with different needs
4. **Tight Coupling**: Difficult to modify one mode without affecting others

---

## New Architecture

### Design Principles

1. **Mode Isolation**: Each mode has its own checkpointer and storage directory
2. **Single Responsibility**: Each module serves only one mode
3. **Symmetry**: All three modes use similar patterns (checkpointer-based)
4. **Shared Infrastructure**: Common utilities (SessionStorage, SessionManager) are reused

### Directory Structure (After)

```
src/components/shared/memory/
├── __init__.py
├── session_manager.py            # Shared: All modes
├── llm_memory.py                 # NEW: LLM mode only
├── basic_agent_checkpointer.py   # NEW: Basic Agent only
└── deep_agent_checkpointer.py    # NEW: Deep Agent only

src/components/shared/storage/
├── session_storage.py            # Shared: File I/O (no change)
└── message_filter.py             # Shared: Filtering (no change)

data/
├── llm/sessions/                 # NEW: LLM mode isolated
├── basicagent/sessions/          # NEW: Basic Agent isolated
└── deepagent/sessions/           # Existing: Deep Agent isolated
```

### Removed Files

- `global_memory.py` - Split into three mode-specific modules
- `memory_sync.py` - Integrated into `deep_agent_checkpointer.py`
- `config.py` - No longer needed (each checkpointer hardcodes its path)
- `unified_checkpointer.py` - Already deprecated
- `persistence/helpers.py` - Integrated into `deep_agent_checkpointer.py`

### Module Responsibilities (After)

#### `session_manager.py` - Shared Infrastructure

**Responsibility**: Unified session lifecycle management for all modes

**Key Methods**:
```python
class SessionManager:
    def __init__(mode: str)  # "llm", "basic", or "deep"

    # Session lifecycle
    def create_new_session() -> str
    def switch_to_session(session_id: str) -> bool
    def delete_session(session_id: str) -> bool

    # Query sessions
    def list_sessions(mode: Optional[str] = None) -> List[Dict]
    def list_all_sessions() -> Dict[str, List[Dict]]  # Group by mode
    def session_exists(session_id: str, mode: Optional[str] = None) -> bool
    def get_session_info(session_id: str) -> Dict
```

**Design**:
- Single instance manages sessions across all modes
- Uses different `SessionStorage` instances per mode
- Supports cross-mode queries (for `/sessions` command)

#### `llm_memory.py` - LLM Mode

**Responsibility**: Simple memory management for LLM mode (no LangGraph)

**Key Methods**:
```python
class LLMMemory:
    def __init__(storage_dir: str = "data/llm/sessions")

    # History operations
    def get_history(session_id: str, max_messages: int = 50) -> List[BaseMessage]
    def add_conversation(session_id: str, user_msg: str, ai_msg: str) -> bool
```

**Design**:
- Does NOT inherit from `BaseCheckpointSaver` (not needed)
- Simple append-based history management
- No graph execution, just message list

**Why not use checkpointer?**
- LLM mode doesn't use LangGraph StateGraph
- Only needs simple history storage
- Avoid unnecessary complexity

#### `basic_agent_checkpointer.py` - Basic Agent Mode

**Responsibility**: LangGraph checkpointer for Basic Agent

**Key Methods**:
```python
class BasicAgentCheckpointer(BaseCheckpointSaver):
    def __init__(storage_dir: str = "data/basicagent/sessions")

    # LangGraph checkpointer interface
    def get_tuple(config: RunnableConfig) -> Optional[CheckpointTuple]
    def put(config, checkpoint, metadata, new_versions) -> RunnableConfig
    def get_next_version(current: Optional[int], channel) -> int
```

**Design**:
- Inherits from LangGraph's `BaseCheckpointSaver`
- Directly reads/writes `SessionStorage` (no dual-memory problem)
- Automatically called by LangGraph during graph execution

**Fixes**:
- Eliminates the MemorySaver + SessionStorage dual-memory issue
- No more overwrite bug (reads existing history before writing)

#### `deep_agent_checkpointer.py` - Deep Agent Mode

**Responsibility**: Checkpointer with HITL support for Deep Agent

**Key Methods**:
```python
class DeepAgentCheckpointer(BaseCheckpointSaver):
    def __init__(storage_dir: str = "data/deepagent/sessions")

    # LangGraph checkpointer interface
    def get_tuple(config) -> Optional[CheckpointTuple]
    def put(config, checkpoint, metadata, new_versions) -> RunnableConfig

    # HITL support (runtime checkpointer)
    def enhance_runtime_input(session_ctx, user_query) -> Dict
    def persist_from_runtime(session_ctx, runtime_checkpointer, ...) -> None
```

**Design**:
- Integrates logic from `GlobalMemoryManager` + `MemorySyncAdapter` + `persistence/helpers.py`
- Uses MemorySaver as runtime checkpointer (for HITL state recovery)
- Syncs runtime state to persistent storage
- Filters out ToolMessage and SystemMessage

**Integration**:
- Absorbs `memory_sync.py`'s Deep-specific logic
- Absorbs `persistence/helpers.py`'s `persist_conversation_state()`
- Self-contained, no external dependencies beyond SessionStorage

---

## Storage Layer (Unchanged)

### `session_storage.py`

**Responsibility**: Low-level file I/O operations

**Key Methods**:
```python
class SessionStorage:
    def __init__(storage_dir: str)

    def load_session(session_id: str) -> List[BaseMessage]
    def save_session(session_id: str, messages: List[BaseMessage], metadata: Dict) -> None
    def list_sessions() -> List[Dict]
    def session_exists(session_id: str) -> bool
    def delete_session(session_id: str) -> bool
```

**Usage**:
- Instantiated by each checkpointer with mode-specific directory
- No changes needed (pure storage abstraction)

### `message_filter.py`

**Responsibility**: Message filtering logic

**Key Methods**:
```python
class MessageFilter:
    def is_system_command(message: str) -> bool
    def should_save_message(user_msg: str, ai_msg: str) -> bool
    def is_system_notification(message: BaseMessage) -> bool
    def filter_message_history(messages: List[BaseMessage]) -> List[BaseMessage]
```

**Usage**:
- Used by all checkpointers to filter messages
- No changes needed

---

## Mode Comparison

### LLM Mode

| Aspect | Before | After |
|--------|--------|-------|
| Module | `global_memory.py` | `llm_memory.py` |
| Directory | `data/llm_basicagent/` (shared with Basic) | `data/llm/sessions/` (isolated) |
| Mechanism | Manual `add_llm_conversation()` | Same (simple append) |
| Checkpointer | None | None (not needed) |

### Basic Agent Mode

| Aspect | Before | After |
|--------|--------|-------|
| Module | `memory_sync.py` | `basic_agent_checkpointer.py` |
| Directory | `data/llm_basicagent/` (shared with LLM) | `data/basicagent/sessions/` (isolated) |
| Mechanism | MemorySaver + persist_from_runtime (buggy) | LangGraph checkpointer (auto) |
| Checkpointer | MemorySaver (in-memory) | BasicAgentCheckpointer (persistent) |
| Issue | Overwrite history bug | Fixed |

### Deep Agent Mode

| Aspect | Before | After |
|--------|--------|-------|
| Module | `global_memory.py` + `memory_sync.py` | `deep_agent_checkpointer.py` |
| Directory | `data/deepagent/sessions/` | Same (no change) |
| Mechanism | MemorySaver + MemorySyncAdapter | Integrated into checkpointer |
| Checkpointer | MemorySaver (runtime) + UnifiedCheckpointer | DeepAgentCheckpointer |
| HITL Support | Yes | Yes (preserved) |

---

## Benefits

### 1. Mode Isolation

- Each mode has independent storage: `data/{llm,basicagent,deepagent}/sessions/`
- No session ID conflicts between modes
- Clear ownership and boundaries

### 2. Bug Fixes

- Basic Agent: Eliminates overwrite bug (checkpointer reads before writing)
- Deep Agent: Preserves HITL support while simplifying architecture

### 3. Modularity

- Each checkpointer is self-contained
- Easy to modify one mode without affecting others
- Clear responsibilities (SRP principle)

### 4. Symmetry

- All three modes follow similar patterns (checkpointer or memory manager)
- Consistent interface for session management
- Easy to understand and maintain

### 5. Simplified Codebase

- Removed `config.py` (no longer needed)
- Removed `global_memory.py` (split into mode-specific modules)
- Removed `persistence/helpers.py` (integrated into Deep checkpointer)
- Clearer module boundaries

---

## Migration Notes

### Session ID Compatibility

After refactoring, sessions are physically separated by mode. When users switch modes:

**Option A: Isolation (Recommended for initial implementation)**
- Each mode starts with a new session
- No automatic history migration
- Simple and safe

**Option B: Migration (Future enhancement)**
- Add optional `--copy-session` flag to `/switch` command
- Copy session file from old mode's directory to new mode's directory
- Requires conflict handling

### Backward Compatibility

**Storage Format**: Unchanged (JSON files with same structure)
- Existing session files can be moved to new directories without modification
- `SessionStorage` API unchanged

**Commands**: Minor updates needed
- `/sessions` - Now shows sessions grouped by mode
- `/restore` - May need mode parameter for cross-mode restore

---

## Summary

The refactoring transforms a shared, tightly-coupled architecture into a modular, mode-specific architecture:

**Old**: One GlobalMemoryManager serves all modes → Conflicts and bugs

**New**: Three independent checkpointers/managers → Clean separation

Each mode now has:
- Its own storage directory
- Its own checkpointer/manager module
- Clear, focused responsibilities

The shared infrastructure (SessionStorage, SessionManager, MessageFilter) remains unchanged and is reused across modes.

---

## Session Commands and Mode Switching

### Session Command Behavior

All session-related commands (`/new`, `/sessions`, `/restore`, `/cleanup`, `/delete_session`, `/clear`) remain functional after refactoring:

**Key Points**:

1. **Commands operate on current mode's storage**
   - `/new` creates session in current mode's directory
   - `/sessions` shows sessions from current mode (or all modes grouped)
   - `/restore` validates session exists in current mode
   - `/cleanup` cleans orphaned sessions in current mode

2. **Cross-mode session access**
   - `/restore` shows helpful error if session exists in different mode:
     ```
     Session 'user_xxx' exists in 'deep' mode, not current mode 'basic'.
     Switch to deep mode first using /mode deep.
     ```

3. **Session isolation by design**
   - Each mode maintains independent sessions
   - No automatic session migration between modes
   - Clear separation prevents confusion

### Mode Switching Behavior

When switching modes using `/switch` or `/mode` commands:

**Behavior**:
1. Automatically loads most recent session from target mode
2. If no session exists in target mode, creates new one
3. Session ID changes when switching modes (expected isolation)

**Example**:
```
User: /switch llm
System: Loaded LLM session: user_20240101_abc123

User: /mode deep
System: Created new deep mode session: user_20240101_ghi789

User: /mode basic
System: Loaded basic agent session: user_20240101_def456
```

**Design Rationale**:
- Prioritizes isolation over continuity
- Different modes have different capabilities
- Prevents conversations from becoming incoherent across mode switches

**SessionManager Updates**:
- Constructor no longer requires `GlobalMemoryManager` parameter
- New methods: `list_all_sessions()`, `session_exists(session_id, mode)`
- Directly accesses `SessionStorage` without intermediate layer

See `integration.md` for detailed implementation examples.
