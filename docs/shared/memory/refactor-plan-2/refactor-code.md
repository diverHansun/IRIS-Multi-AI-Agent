# Code Refactoring Details

## Overview

This document details how to deconstruct existing files and preserve Deep Agent functionality during the memory module refactoring.

---

## Files to Remove

### 1. `src/components/shared/memory/config.py`

**Status**: DELETE

**Reason**:
- Each checkpointer now hardcodes its own storage directory
- No need for central configuration mapping

**Before**:
```python
AGENT_MODE_STORAGE_MAP = {
    "basic": "data/llm_basicagent/sessions",
    "llm": "data/llm_basicagent/sessions",
    "deep": "data/deepagent/sessions",
}
```

**After**:
```python
# In each checkpointer
class LLMMemory:
    def __init__(self, storage_dir: str = "data/llm/sessions"):
        self.storage = SessionStorage(storage_dir)

class BasicAgentCheckpointer:
    def __init__(self, storage_dir: str = "data/basicagent/sessions"):
        self.storage = SessionStorage(storage_dir)

class DeepAgentCheckpointer:
    def __init__(self, storage_dir: str = "data/deepagent/sessions"):
        self.storage = SessionStorage(storage_dir)
```

### 2. `src/components/shared/memory/unified_checkpointer.py`

**Status**: DELETE

**Reason**: Already deprecated, not used

### 3. `src/components/shared/persistence/helpers.py`

**Status**: DELETE (after integration)

**Reason**: `persist_conversation_state()` function will be integrated into `DeepAgentCheckpointer`

---

## File Deconstruction

### `global_memory.py` - Split into Three Modules

#### Original Structure

```python
# src/components/shared/memory/global_memory.py

class GlobalChatMessageHistory(BaseChatMessageHistory):
    """Per-session message history (in-memory cache)"""
    def __init__(session_id, global_manager, mode):
        self._messages = []
        self._load_messages()  # Load from SessionStorage

    def add_messages(messages):
        self._messages.extend(messages)
        # Auto-save to storage
        self.global_manager._save_session_async(session_id, self._messages, mode)

class GlobalMemoryManager:
    """Manages session histories and storage"""

    # Storage management
    def __init__(agent_mode: str, max_messages: int):
        self._session_histories: Dict[str, GlobalChatMessageHistory] = {}
        self._storage = self._get_or_create_storage(agent_mode)

    def get_storage_by_mode(mode: str) -> SessionStorage:
        # Returns SessionStorage instance for the mode

    # LLM mode operations
    def add_llm_conversation(session_id, user_msg, ai_msg):
        """LLM mode: Add conversation directly"""
        history = self.get_session_history(session_id)
        history.add_messages([
            HumanMessage(content=user_msg),
            AIMessage(content=ai_msg)
        ])

    # Session history operations
    def get_session_history(session_id, agent_mode) -> GlobalChatMessageHistory:
        """Get cached history or create new"""
        cache_key = f"{session_id}:{agent_mode}"
        if cache_key not in self._session_histories:
            self._session_histories[cache_key] = GlobalChatMessageHistory(...)
        return self._session_histories[cache_key]

    # Session management operations (should be in SessionManager)
    def list_sessions() -> List[Dict]:
        return self._storage.list_sessions()

    def session_exists(session_id) -> bool:
        return self._storage.session_exists(session_id)

    def get_session_info(session_id) -> Dict:
        # Returns metadata about session
```

#### Deconstruction Strategy

**Step 1: Extract LLM Operations → `llm_memory.py`**

```python
# NEW: src/components/shared/memory/llm_memory.py

class LLMMemory:
    """
    Simple memory manager for LLM mode.

    Extracted from GlobalMemoryManager.add_llm_conversation()
    """

    def __init__(self, storage_dir: str = "data/llm/sessions"):
        self.storage = SessionStorage(storage_dir)
        self.max_messages = 50

    def get_history(self, session_id: str, max_messages: int = None) -> List[BaseMessage]:
        """
        Load history from storage.

        Replaces: GlobalMemoryManager.get_session_history() for LLM mode
        """
        messages = self.storage.load_session(session_id) or []
        limit = max_messages or self.max_messages
        return messages[-limit:] if len(messages) > limit else messages

    def add_conversation(self, session_id: str, user_msg: str, ai_msg: str) -> bool:
        """
        Add conversation to history.

        Replaces: GlobalMemoryManager.add_llm_conversation()
        """
        try:
            # Load existing (merge strategy - fix overwrite bug)
            messages = self.storage.load_session(session_id) or []

            # Append new
            messages.extend([
                HumanMessage(content=user_msg),
                AIMessage(content=ai_msg)
            ])

            # Save
            self.storage.save_session(session_id, messages)
            return True
        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            return False
```

**Step 2: Extract Session Management → `session_manager.py` (enhance existing)**

```python
# ENHANCE: src/components/shared/memory/session_manager.py

class SessionManager:
    """
    Session lifecycle management for all modes.

    Absorbs session management methods from GlobalMemoryManager.
    """

    def __init__(self, mode: str = "basic"):
        self.mode = mode
        self.storage_dirs = {
            "llm": "data/llm/sessions",
            "basic": "data/basicagent/sessions",
            "deep": "data/deepagent/sessions",
        }
        self.current_session_id: Optional[str] = None

    # Absorbs: GlobalMemoryManager.list_sessions()
    def list_sessions(self, mode: Optional[str] = None) -> List[Dict]:
        target_mode = mode or self.mode
        storage = SessionStorage(self.storage_dirs[target_mode])
        return storage.list_sessions()

    # Absorbs: GlobalMemoryManager.session_exists()
    def session_exists(self, session_id: str, mode: Optional[str] = None) -> bool:
        target_mode = mode or self.mode
        storage = SessionStorage(self.storage_dirs[target_mode])
        return storage.session_exists(session_id)

    # Absorbs: GlobalMemoryManager.get_session_info()
    def get_session_info(self, session_id: str, mode: Optional[str] = None) -> Dict:
        target_mode = mode or self.mode
        storage = SessionStorage(self.storage_dirs[target_mode])
        messages = storage.load_session(session_id) or []

        return {
            "session_id": session_id,
            "message_count": len(messages),
            "mode": target_mode,
            "last_updated": storage.get_last_modified(session_id),
        }

    # NEW: List sessions from all modes
    def list_all_sessions(self) -> Dict[str, List[Dict]]:
        """For /sessions command"""
        return {
            mode: SessionStorage(dir).list_sessions()
            for mode, dir in self.storage_dirs.items()
        }

    # NEW: Create session
    def create_new_session(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        session_id = f"user_{timestamp}_{unique_id}"

        storage = SessionStorage(self.storage_dirs[self.mode])
        storage.save_session(session_id, [])  # Initialize empty

        self.current_session_id = session_id
        return session_id
```

**Step 3: Deep Agent Operations → Handled by `memory_sync.py` (see next section)**

---

### `memory_sync.py` - Integrate into `deep_agent_checkpointer.py`

#### Original Structure

```python
# src/components/shared/memory/memory_sync.py

class MemorySyncAdapter:
    """
    Coordinates runtime and persistent memory.

    Used by:
    - Deep Agent: enhance_runtime_input, persist_from_runtime
    - Basic Agent: persist_from_runtime (buggy)
    """

    def __init__(global_memory: GlobalMemoryManager, agent_mode: str):
        self.global_memory = global_memory
        self.agent_mode = agent_mode
        self.storage = global_memory.get_storage_by_mode(agent_mode)

    def enhance_runtime_input(session_ctx, user_query, max_history=10):
        """Deep mode: Inject history into input"""
        stored_messages = self.storage.load_session(session_ctx.session_id)
        messages = stored_messages[-max_history:] if stored_messages else []
        messages.append(HumanMessage(content=user_query))
        return {"messages": messages}

    def persist_from_runtime(session_ctx, runtime_checkpointer, runtime_config, agent_state):
        """
        Deep mode + Basic mode: Sync runtime to storage

        ISSUE: Basic mode overwrites history (bug)
        """
        # Extract messages from agent_state or runtime checkpoint
        messages_to_persist = agent_state.get("messages", [])

        # Flatten and filter
        flattened = self._flatten_messages(messages_to_persist)
        filtered = [m for m in flattened if isinstance(m, (HumanMessage, AIMessage))]

        # Deduplicate
        deduplicated = self._deduplicate_messages(filtered)

        # Save (overwrites existing - BUG for Basic mode)
        self.storage.save_session(session_ctx.session_id, deduplicated)
```

#### Integration Strategy

**Create `deep_agent_checkpointer.py` - Absorb Deep-specific logic**

```python
# NEW: src/components/shared/memory/deep_agent_checkpointer.py

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

class DeepAgentCheckpointer(BaseCheckpointSaver):
    """
    Deep Agent checkpointer with HITL support.

    Integrates:
    - MemorySyncAdapter (enhance_runtime_input, persist_from_runtime)
    - persistence/helpers.py (persist_conversation_state)
    - GlobalMemoryManager (Deep mode operations)
    """

    def __init__(self, storage_dir: str = "data/deepagent/sessions"):
        super().__init__()
        self.storage = SessionStorage(storage_dir)
        self.runtime_checkpointer = MemorySaver()  # For HITL

    # From MemorySyncAdapter.enhance_runtime_input()
    def enhance_runtime_input(
        self,
        session_id: str,
        user_query: str,
        max_history: int = 10
    ) -> Dict[str, Any]:
        """
        Inject history into runtime input.

        Used by Deep Agent to load history before execution.
        """
        messages = []
        try:
            stored_messages = self.storage.load_session(session_id)
            if stored_messages:
                messages = stored_messages[-max_history:]
                logger.debug(f"Loaded {len(messages)} historical messages")
        except Exception as exc:
            logger.warning(f"Failed to load history: {exc}")

        messages.append(HumanMessage(content=user_query))
        return {"messages": messages}

    # From MemorySyncAdapter.persist_from_runtime() + persistence/helpers.py
    def persist_from_runtime(
        self,
        session_id: str,
        runtime_checkpointer: Any,
        runtime_config: Dict[str, Any],
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Persist runtime state to storage.

        Extracts messages from agent_state or runtime checkpoint,
        filters to Human/AI only, and saves to SessionStorage.

        This preserves Deep Agent's HITL state recovery capability.
        """
        # Extract messages
        messages_to_persist = []
        if isinstance(agent_state, dict):
            messages_to_persist = agent_state.get("messages", [])

        # Fallback: try runtime checkpoint
        if not messages_to_persist and runtime_checkpointer:
            try:
                checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
                if checkpoint_tuple:
                    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
                    messages_to_persist = channel_values.get("messages", [])
            except Exception as exc:
                logger.warning(f"Failed to read runtime checkpoint: {exc}")

        # Flatten and filter
        flattened = self._flatten_messages(messages_to_persist)
        filtered = [
            m for m in flattened
            if isinstance(m, (HumanMessage, AIMessage))
        ]

        if not filtered:
            logger.warning(f"No messages to persist for session {session_id}")
            return False

        # Deduplicate
        deduplicated = self._deduplicate_messages(filtered)

        # Save
        try:
            self.storage.save_session(session_id, deduplicated)
            logger.debug(f"Persisted {len(deduplicated)} messages for {session_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to persist: {exc}")
            return False

    # From MemorySyncAdapter._flatten_messages()
    @staticmethod
    def _flatten_messages(entries: Any) -> List[BaseMessage]:
        """Extract BaseMessage instances from nested structures"""
        # (Keep implementation from MemorySyncAdapter)

    # From MemorySyncAdapter._deduplicate_messages()
    @staticmethod
    def _deduplicate_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
        """Remove duplicate messages"""
        # (Keep implementation from MemorySyncAdapter)

    # LangGraph checkpointer interface (for future use)
    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Load checkpoint from storage (optional implementation)"""
        pass

    def put(self, config, checkpoint, metadata, new_versions) -> RunnableConfig:
        """Save checkpoint to storage (optional implementation)"""
        pass
```

**Key Points**:
- Keeps Deep Agent's HITL capability (MemorySaver as runtime checkpointer)
- Integrates `enhance_runtime_input()` for history injection
- Integrates `persist_from_runtime()` for state sync
- Absorbs `persist_conversation_state()` from `persistence/helpers.py`

---

## Files to Preserve (Deep Agent Dependencies)

### Critical Methods from `memory_sync.py`

**Must preserve in `DeepAgentCheckpointer`**:

1. **`enhance_runtime_input()`**
   - Used by: Deep Agent service to inject history before execution
   - Location: `src/application/services/agent/deep/streaming/conversation.py`

2. **`persist_from_runtime()`**
   - Used by: Deep Agent service after execution
   - Location: `src/application/services/agent/deep/streaming/conversation.py`

3. **`_flatten_messages()`**
   - Helper for extracting messages from checkpoint structures
   - Keep as static method

4. **`_deduplicate_messages()`**
   - Helper for removing duplicate messages
   - Keep as static method

### Critical Function from `persistence/helpers.py`

**Must integrate into `DeepAgentCheckpointer`**:

```python
# From persistence/helpers.py
async def persist_conversation_state(
    session_ctx,
    runtime_checkpointer,
    runtime_config,
    agent_memory_sync,
    reason: str = "normal",
    ctx=None
) -> bool:
```

**Integration approach**:
- The logic in `persist_conversation_state()` essentially calls `memory_sync.persist_from_runtime()`
- In new architecture, this becomes: `deep_checkpointer.persist_from_runtime()`
- Callers update: `agent_memory_sync.persist_from_runtime()` → `deep_checkpointer.persist_from_runtime()`

---

## Update Call Sites

### Deep Agent Service Updates

**File**: `src/application/services/agent/deep/streaming/conversation.py`

**Before**:
```python
from src.components.shared.memory import MemorySyncAdapter
from src.components.shared.persistence import persist_conversation_state

# Initialize
ctx.memory_sync = MemorySyncAdapter(ctx.global_memory, agent_mode="deep")

# Before execution
input_data = ctx.memory_sync.enhance_runtime_input(session_ctx, query)

# After execution
ctx.memory_sync.persist_from_runtime(session_ctx, runtime_checkpointer, ...)

# On timeout/error
await persist_conversation_state(session_ctx, runtime_checkpointer, ...)
```

**After**:
```python
from src.components.shared.memory import DeepAgentCheckpointer

# Initialize
ctx.deep_checkpointer = DeepAgentCheckpointer()

# Before execution
input_data = ctx.deep_checkpointer.enhance_runtime_input(ctx.session_id, query)

# After execution
ctx.deep_checkpointer.persist_from_runtime(ctx.session_id, runtime_checkpointer, ...)

# On timeout/error
ctx.deep_checkpointer.persist_from_runtime(ctx.session_id, runtime_checkpointer, ...)
```

**Key changes**:
- Replace `MemorySyncAdapter` with `DeepAgentCheckpointer`
- Replace `persist_conversation_state()` with `deep_checkpointer.persist_from_runtime()`
- Simpler API (no need for `GlobalMemoryManager`)

---

## Summary

### Removed Files
- `config.py` - No longer needed
- `unified_checkpointer.py` - Already deprecated
- `persistence/helpers.py` - Integrated into `DeepAgentCheckpointer`

### Deconstructed Files
- `global_memory.py` → Split into:
  - `llm_memory.py` (LLM operations)
  - `session_manager.py` (session management, enhanced)
  - Deep operations absorbed by `memory_sync.py`

- `memory_sync.py` → Transformed into:
  - `deep_agent_checkpointer.py` (Deep-specific, self-contained)
  - Basic Agent no longer uses it

### Created Files
- `llm_memory.py` - LLM mode memory manager
- `basic_agent_checkpointer.py` - Basic Agent checkpointer
- `deep_agent_checkpointer.py` - Deep Agent checkpointer (integrates MemorySyncAdapter + persistence helpers)

### Preserved Functionality
- Deep Agent HITL support (MemorySaver + sync logic)
- Deep Agent history injection (`enhance_runtime_input`)
- Deep Agent state persistence (`persist_from_runtime`)
- All helper methods (`_flatten_messages`, `_deduplicate_messages`)
