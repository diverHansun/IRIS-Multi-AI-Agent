# Deep Agent Memory Persistence Bug Fix Summary

## Problem Diagnosis

### Symptom
Only AIMessages were being saved to session storage, HumanMessages were lost.

Example of problematic session file:
```json
{
  "messages": [
    {"type": "AIMessage", "content": "..."},
    {"type": "AIMessage", "content": "..."}
  ]
}
```

Expected:
```json
{
  "messages": [
    {"type": "HumanMessage", "content": "user question 1"},
    {"type": "AIMessage", "content": "ai response 1"},
    {"type": "HumanMessage", "content": "user question 2"},
    {"type": "AIMessage", "content": "ai response 2"}
  ]
}
```

### Root Cause Analysis

The bug had TWO critical issues:

#### Issue 1: Using event_handler.last_agent_state instead of runtime_checkpointer

**Location:** `src/application/services/agent/deep/streaming/conversation.py:327-335`

**Problem:**
```python
# OLD CODE (BUGGY)
final_state = event_handler.last_agent_state
deep_checkpointer.persist_from_runtime(
    session_id,
    runtime_checkpointer,
    runtime_config,
    final_state,  # This only contains the last update chunk!
)
```

**Why it's wrong:**
- `event_handler.last_agent_state` comes from the `stream_mode="updates"` stream
- It only captures the LAST update payload, which typically contains only the final AIMessage
- The HumanMessage from user input is not included in this last update

**How streaming works:**
1. User sends "Hello" -> Creates HumanMessage
2. LangGraph processes it -> Emits updates with intermediate states
3. AI responds "Hi" -> Last update only contains AIMessage
4. `event_handler.last_agent_state` = {"messages": [AIMessage("Hi")]}
5. Only AIMessage gets persisted!

#### Issue 2: Merging instead of replacing

**Location:** `src/components/shared/memory/deep_agent_checkpointer.py:99-109`

**Problem:**
```python
# OLD CODE (BUGGY)
existing = self.storage.load_session(session_id) or []
merged = existing + filtered  # This causes duplication!
deduplicated = self._deduplicate_messages(merged)
```

**Why it's wrong:**
- Messages from `runtime_checkpointer` already contain COMPLETE conversation history
- MemorySaver maintains full state across turns
- Merging with `existing` creates duplicates
- Even with deduplication, this approach is conceptually wrong

**Correct understanding:**
- MemorySaver checkpoint = complete conversation history (source of truth)
- SessionStorage = persistent copy of that history
- Each persist operation should REPLACE, not MERGE

## The Fix

### Fix 1: Use runtime_checkpointer as the source

**File:** `src/application/services/agent/deep/streaming/conversation.py`

```python
# FIXED CODE
# Do NOT use event_handler.last_agent_state for persistence!
# It only contains the last update chunk, which may miss HumanMessages.
deep_checkpointer.persist_from_runtime(
    session_id,
    runtime_checkpointer,
    runtime_config,
    agent_state=None,  # Force using runtime_checkpointer
)

# event_handler.last_agent_state is still OK for result preparation
final_state = event_handler.last_agent_state  # Only for display
result = agent.prepare_stream_result(query, session_id, final_state, ...)
```

**Why this works:**
- `persist_from_runtime()` will call `runtime_checkpointer.get_tuple()`
- This retrieves the COMPLETE checkpoint with full conversation history
- Includes all HumanMessages and AIMessages

### Fix 2: Replace instead of merge

**File:** `src/components/shared/memory/deep_agent_checkpointer.py`

```python
# FIXED CODE
# The messages from runtime_checkpointer already contain full history.
# Do NOT merge with existing session - just replace it.
existing = self.storage.load_session(session_id) or []  # For logging only
logger.debug("[PERSIST] Existing session messages: %d", len(existing))

# Use filtered messages directly (they are already the complete history)
deduplicated = self._deduplicate_messages(filtered)  # Only remove consecutive dupes
trimmed = self._trim_messages(deduplicated)

# Save (replaces existing file)
self.storage.save_session(session_id, trimmed, metadata=metadata)
```

### Fix 3: Improved deduplication logic

**File:** `src/components/shared/memory/deep_agent_checkpointer.py`

```python
# OLD: Removed ALL duplicates (breaks if user asks same question twice)
# NEW: Only remove CONSECUTIVE duplicates

def _deduplicate_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
    """Remove consecutive duplicates only."""
    if not messages:
        return []

    deduped: List[BaseMessage] = [messages[0]]
    for msg in messages[1:]:
        prev = deduped[-1]
        # Only remove if both type and content match the previous message
        if (type(msg).__name__ == type(prev).__name__ and
            msg.content == prev.content):
            continue  # Skip consecutive duplicate
        deduped.append(msg)

    return deduped
```

**Why this is better:**
- Preserves legitimate repeated questions/responses
- Only removes true bugs (same message appearing twice in a row)
- More robust behavior

## Verification

### Test Results

Created `test_memory_simple.py` to verify the fix:

```
Scenario 1: First turn
Input: [HumanMessage("Hello"), AIMessage("Hi")]
Saved: [HumanMessage("Hello"), AIMessage("Hi")] ✓

Scenario 2: Second turn
Input: [HumanMessage("Hello"), AIMessage("Hi"), HumanMessage("What is 2+2?"), AIMessage("4")]
Saved: [HumanMessage("Hello"), AIMessage("Hi"), HumanMessage("What is 2+2?"), AIMessage("4")] ✓

Final counts:
  HumanMessages: 2 ✓
  AIMessages: 2 ✓

Result: SUCCESS
```

### Debug Logging Added

Enhanced logging in `deep_agent_checkpointer.py` to track the entire persistence flow:

```
[PERSIST] Got N messages from agent_state/runtime checkpoint
[PERSIST] Messages to persist (raw): ...
[FILTER] Input: X, Flattened: Y, Filtered: Z (Human: A, AI: B)
[PERSIST] After filtering: N conversational messages
[PERSIST] Existing session messages: M
[PERSIST] After deduplication: N messages (no merge, direct replacement)
[PERSIST] After trimming: N final messages
```

## Architecture Understanding

### Dual Checkpointer Design

```
┌─────────────────────────────────────────────────────────┐
│                    Conversation Flow                    │
└─────────────────────────────────────────────────────────┘

User Query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  1. enhance_runtime_input()                             │
│     - Load history from SessionStorage (if first query) │
│     - Inject into runtime input                         │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  2. runtime.astream()                                   │
│     - MemorySaver automatically checkpoints state       │
│     - Includes HumanMessage, AIMessage, ToolMessage,    │
│       __interrupt__, etc.                               │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  3. persist_from_runtime()                              │
│     - Extract from MemorySaver checkpoint (complete)    │
│     - Filter to HumanMessage + AIMessage only           │
│     - Save to SessionStorage (JSON file)                │
└─────────────────────────────────────────────────────────┘
```

**Key Principles:**
1. **MemorySaver** = Runtime checkpoint (in-memory, full state, supports HITL)
2. **SessionStorage** = Persistent storage (JSON files, conversational messages only)
3. **MemorySaver is source of truth** during execution
4. **SessionStorage persists across program restarts**
5. **No merging** - MemorySaver checkpoint already contains full history

## Lessons Learned

1. **Event streams != Full state**
   - Stream chunks are incremental updates
   - Use checkpointer.get_tuple() for complete state

2. **Understand data flow**
   - MemorySaver maintains full history automatically
   - Don't assume you need to manually merge histories

3. **Test edge cases**
   - User asks same question twice (should not dedupe)
   - Program restart mid-conversation
   - Multiple turns in same session

4. **Debug logging is essential**
   - Add [PREFIX] tags for easy grepping
   - Log message counts and types at each step
   - Log first few messages for verification

## Files Modified

1. `src/application/services/agent/deep/streaming/conversation.py`
   - Stop using `event_handler.last_agent_state` for persistence
   - Pass `agent_state=None` to force reading from runtime_checkpointer

2. `src/components/shared/memory/deep_agent_checkpointer.py`
   - Remove merge logic (existing + filtered)
   - Use filtered messages directly (already complete history)
   - Improve deduplication to only remove consecutive duplicates
   - Add comprehensive debug logging

## Testing Recommendations

After applying these fixes:

1. Delete existing test session files in `data/deepagent/sessions/`
2. Run a new conversation with 2-3 turns
3. Check the session JSON file:
   - Should have equal or similar numbers of HumanMessage and AIMessage
   - Messages should alternate (roughly): Human, AI, Human, AI, ...
   - No missing user questions

4. Test edge cases:
   - Ask the same question twice (both should be saved)
   - Restart program and continue conversation
   - Use HITL approval (should not affect message persistence)

## Migration Notes

**No data migration required** - old session files will continue to work:
- Old files with only AIMessages can still be loaded
- New conversations will save correctly
- Consider clearing old incomplete sessions if desired

**Backward compatibility:**
- `SessionStorage._dict_to_message()` already handles gracefully
- Unknown message types convert to HumanMessage for compatibility
