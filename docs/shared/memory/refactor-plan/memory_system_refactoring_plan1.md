# Memory System Refactoring Plan

## Architecture Overview

### Current Implementation Characteristics

Our multi-engine system uses a **dual-checkpointer architecture** for Deep mode with unified persistence:

```
Deep Mode (HITL support)
  - runtime_checkpointer (MemorySaver): Full state including ToolMessage
  - storage_checkpointer (UnifiedCheckpointer): Persistent storage, HumanMessage/AIMessage only
  - MemorySyncAdapter: Bidirectional sync between runtime and storage

Basic Mode
  - UnifiedCheckpointer: Direct persistent storage

LLM Mode
  - GlobalMemoryManager: Direct persistent storage via add_llm_conversation()

All modes share:
  - GlobalMemoryManager -> SessionStorage (file system)
  - session_id as unified key across modes
```

### Comparison with Official Implementation

| Aspect | Official DeepAgents | Our Implementation |
|--------|-------------------|-------------------|
| Checkpointer | Single (MemorySaver/PostgresSaver) | Dual (runtime + storage) for Deep mode |
| HITL Support | Direct via single checkpointer | Via runtime_checkpointer with full state |
| Persistence | User choice (optional) | Required (file-based via UnifiedCheckpointer) |
| Storage Filter | Stores all messages | Filters ToolMessage for persistence |
| Multi-engine | Not applicable | Deep/Basic/LLM share session_id |
| Long-term Memory | File-based via CompositeBackend | Not implemented (planned future) |

**Key Design Rationale**: Our dual-checkpointer approach enables HITL with full state recovery while maintaining clean persistent storage without ToolMessage bloat.

## Problem Analysis

### Root Cause

The current issues stem from **namespace isolation mismatch**, not architectural problems:

1. **Namespace Generation**: SessionContext generates `checkpoint_ns` (e.g., "deep_agent::zhipu::research")
2. **Storage Ignores Namespace**: UnifiedCheckpointer.get_tuple() only uses `thread_id` (line 124)
3. **Requirement Conflict**: User expects session_id to share history across providers, but namespace implies isolation

### Pain Points

**Issue 1: Cannot read history after provider switch**
```python
# User workflow
session_id = "user123"
# 1. Query with zhipu -> saves to session_id="user123"
# 2. Switch to openai -> SessionContext generates different checkpoint_ns
# 3. UnifiedCheckpointer reads session_id="user123" (ignores checkpoint_ns)
# 4. History loads correctly BUT namespace confusion exists in code
```

**Issue 2: Potential duplicate writes** (verify if still exists)
- persist_from_runtime() writes once
- _record_conversation() may write again (needs verification)

## Solution

### Step 1: Remove Namespace Isolation

**Modify SessionContext** to not use checkpoint_ns for storage routing:

```python
# src/components/shared/memory/session_context.py
def build_runtime_config(self, base_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = dict(base_config) if base_config else {}
    configurable = dict(config.get("configurable", {}))
    configurable["thread_id"] = self.thread_id()
    # REMOVE: configurable["checkpoint_ns"] = self.checkpoint_namespace()
    if self.checkpoint_id:
        configurable["checkpoint_id"] = self.checkpoint_id
    config["configurable"] = configurable
    return config
```

**Rationale**:
- All modes (deep/basic/llm) use same session_id for storage
- Provider/model switching preserves full conversation history
- checkpoint_ns was intended for isolation but conflicts with multi-engine sharing requirement

### Step 2: Verify Single Write Path

**Check for _record_conversation() calls**:
```bash
grep -r "_record_conversation" src/
```

If found, ensure it's not called in parallel with persist_from_runtime(). Only persist_from_runtime() should write to storage.

### Step 3: Maintain Dual-Checkpointer for Deep Mode

**No changes needed** - current design is correct:

- runtime_checkpointer: Required for HITL state recovery
- storage_checkpointer: Required for clean persistent storage
- MemorySyncAdapter: Required for sync logic

### Step 4: Verification Testing

Test scenarios:

1. **Cross-provider memory**:
   - session_id="test", zhipu: "Hello" -> response saved
   - Switch to openai: "What did I just say?" -> should recall "Hello"

2. **Deep mode HITL**:
   - Trigger tool approval -> interrupt occurs
   - Resume with approval -> should restore full state correctly

3. **Mode switching**:
   - Deep mode: conversation
   - Switch to Basic mode: should see same history
   - Switch to LLM mode: should see same history

## Post-Refactoring Architecture

```
User Query (session_id)
        |
        v
+-------+--------+--------+
| Deep  | Basic  |  LLM   |
+-------+--------+--------+
        |
        v (all write to same session_id)
+----------------------------------+
|  UnifiedCheckpointer             |
|  - get_tuple(thread_id)          |
|  - put(filtered messages)        |
+----------------------------------+
        |
        v
+----------------------------------+
|  GlobalMemoryManager             |
|  - get_session_history(session_id)|
+----------------------------------+
        |
        v
+----------------------------------+
|  SessionStorage (file system)    |
|  - data/sessions/{session_id}.json|
+----------------------------------+

Deep Mode Detail:
  User Query
      |
      v
  MemorySyncAdapter.load_into_runtime()
      |
      v
  runtime_checkpointer (MemorySaver) <- full state
      |
      v
  Agent Execution (with HITL support)
      |
      v
  MemorySyncAdapter.persist_from_runtime()
      |
      v (filter ToolMessage)
  storage_checkpointer (UnifiedCheckpointer)
```

## Implementation Checklist

- [ ] Remove checkpoint_ns from SessionContext.build_runtime_config()
- [ ] Verify no _record_conversation() duplicate writes
- [ ] Update SessionContext documentation
- [ ] Test cross-provider memory sharing
- [ ] Test Deep mode HITL functionality
- [ ] Test cross-mode memory sharing (deep/basic/llm)
- [ ] Update relevant architecture docs

## Future Considerations

**Long-term Memory (Optional)**:
- Could implement CompositeBackend-style routing for `/memories/` prefix
- Agent instructions, preferences stored separately from conversation history
- Not required for current functionality - conversation history is sufficient
