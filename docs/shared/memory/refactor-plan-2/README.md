# Memory Module Refactoring Plan

## Overview

This refactoring transforms the memory module from a shared, tightly-coupled architecture to a modular, mode-specific architecture. Each mode (LLM, Basic Agent, Deep Agent) will have its own checkpointer with isolated storage.

## Background

### Current Problems

1. **Session ID Conflicts**: Basic and LLM modes share `data/llm_basicagent/`, causing conflicts
2. **Overwrite Bug**: Basic Agent overwrites existing history when saving
3. **Mixed Responsibilities**: `GlobalMemoryManager` serves multiple modes with different needs
4. **Tight Coupling**: Changes to one mode affect others

### Root Cause

The dual-memory architecture in Basic Agent mode:
- **Runtime**: MemorySaver (in-memory, may be empty after engine switch)
- **Persistent**: SessionStorage (disk, has history)
- **Problem**: `persist_from_runtime()` overwrites disk with runtime's incomplete state

## Solution

### Core Design

1. **Mode Isolation**: Three independent checkpointers with separate storage directories
2. **Symmetry**: All modes follow similar patterns (checkpointer-based)
3. **Shared Infrastructure**: SessionStorage and SessionManager reused across modes

### New Structure

```
src/components/shared/memory/
├── session_manager.py            # Shared: All modes
├── llm_memory.py                 # LLM mode only
├── basic_agent_checkpointer.py   # Basic Agent only
└── deep_agent_checkpointer.py    # Deep Agent only

data/
├── llm/sessions/                 # LLM isolated
├── basicagent/sessions/          # Basic Agent isolated
└── deepagent/sessions/           # Deep Agent isolated
```

## Documentation

### [architecture.md](./architecture.md)

Detailed architecture comparison:
- Old architecture structure and problems
- New architecture design and benefits
- Module responsibilities before and after
- Data flow changes
- Storage layer details

**Read this first** to understand the overall design.

### [refactor-code.md](./refactor-code.md)

Code-level refactoring details:
- Files to remove and why
- How to deconstruct `global_memory.py`
- How to integrate `memory_sync.py` into `deep_agent_checkpointer.py`
- Preserving Deep Agent functionality
- Critical methods to keep

**Read this** before writing code to understand what needs to be changed.

### [integration.md](./integration.md)

Integration guide for services:
- LLM mode integration steps
- Basic Agent integration steps
- Deep Agent integration steps
- Session management updates
- Engine switch updates
- Testing procedures

**Read this** to understand how to update service layers.

## Implementation Plan

### Phase 1: Preparation (1-2 days)

**Goal**: Create new modules without breaking existing code

Tasks:
- Create `llm_memory.py` with `LLMMemory` class
- Create `basic_agent_checkpointer.py` with `BasicAgentCheckpointer` class
- Create `deep_agent_checkpointer.py` with `DeepAgentCheckpointer` class
- Enhance `session_manager.py` with cross-mode support
- Write unit tests for new modules

**No existing code changes yet** - just add new files.

### Phase 2: LLM Mode Migration (0.5 day)

**Goal**: Migrate LLM mode to new architecture

Tasks:
- Update `src/application/services/llm/conversation.py`
- Replace `global_memory.add_llm_conversation()` with `llm_memory.add_conversation()`
- Update initialization code
- Test: Verify LLM conversations save correctly to `data/llm/sessions/`

**Risk**: Low (LLM mode is simple, no LangGraph involved)

### Phase 3: Basic Agent Migration (1 day)

**Goal**: Fix Basic Agent overwrite bug

Tasks:
- Update `src/agents/basicagents/adapters/base_adapter.py`
- Replace `MemorySaver` with `BasicAgentCheckpointer` in agent creation
- Update `src/application/services/agent/basic/conversation.py`
- Remove `persist_from_runtime()` calls (checkpointer handles it)
- Test: Verify history is preserved after engine switch

**Risk**: Medium (need to verify LangGraph integration works correctly)

**Testing**:
```
1. Create session with 6 messages
2. /switch llm, /switch agent (trigger engine switch)
3. Send new message
4. Verify all 7 messages are in data/basicagent/sessions/*.json
```

### Phase 4: Deep Agent Migration (1 day)

**Goal**: Migrate Deep Agent without breaking HITL

Tasks:
- Update `src/application/services/agent/deep/streaming/conversation.py`
- Replace `MemorySyncAdapter` with `DeepAgentCheckpointer`
- Remove `persist_conversation_state()` import
- Update error/timeout handlers
- Test: Verify HITL still works

**Risk**: Medium-High (must preserve HITL functionality)

**Testing**:
```
1. Trigger HITL approval prompt
2. Interrupt and resume
3. Verify state recovery works
4. Check data/deepagent/sessions/*.json for correct messages
```

### Phase 5: Commands and Engine Switch (0.5 day)

**Goal**: Update CLI commands for new architecture

Tasks:
- Update `/sessions` command to group by mode
- Update `/restore` command to support cross-mode restore
- Update `/switch` command to preserve user selection
- Update CLI context structure
- Test all commands

**Risk**: Low (mostly display changes)

### Phase 6: Cleanup (0.5 day)

**Goal**: Remove old code and update documentation

Tasks:
- Delete `global_memory.py`
- Delete `memory_sync.py`
- Delete `config.py`
- Delete `persistence/helpers.py`
- Update `__init__.py` exports
- Update architecture documentation
- Final integration testing

**Verification**:
- Run full test suite
- Test all three modes
- Test mode switching
- Test session management commands

## File Changes Summary

### Files to Delete
- `src/components/shared/memory/global_memory.py` (450 lines)
- `src/components/shared/memory/memory_sync.py` (258 lines)
- `src/components/shared/memory/config.py` (46 lines)
- `src/components/shared/memory/unified_checkpointer.py` (deprecated)
- `src/components/shared/persistence/helpers.py` (119 lines)

**Total deleted**: ~873 lines

### Files to Create
- `src/components/shared/memory/llm_memory.py` (~100 lines)
- `src/components/shared/memory/basic_agent_checkpointer.py` (~200 lines)
- `src/components/shared/memory/deep_agent_checkpointer.py` (~300 lines)

**Total new**: ~600 lines

### Files to Enhance
- `src/components/shared/memory/session_manager.py` (+100 lines)

### Net Change
- **Deleted**: 873 lines
- **Added**: 700 lines
- **Net**: -173 lines (simpler codebase!)

## Benefits

### 1. Bug Fixes
- Basic Agent overwrite bug eliminated
- `/restore` + `/switch` interaction fixed
- Session ID conflicts resolved

### 2. Architecture Improvements
- Clear module boundaries (SRP principle)
- Mode isolation (easier to modify)
- Reduced coupling (easier to test)

### 3. Code Quality
- 173 fewer lines of code
- Simpler logic (no dual-memory complexity)
- Better symmetry (all modes follow similar patterns)

## Risks and Mitigations

### Risk 1: Breaking Deep Agent HITL

**Mitigation**:
- Preserve all MemorySyncAdapter logic in DeepAgentCheckpointer
- Extensive HITL testing before deployment
- Keep old code in git history for rollback

### Risk 2: Data Loss During Migration

**Mitigation**:
- Backup `data/` directory before migration
- SessionStorage format unchanged (just directory reorganization)
- Gradual rollout (one mode at a time)

### Risk 3: Performance Impact

**Mitigation**:
- New checkpointers use same SessionStorage (no change in I/O)
- Basic Agent: Actually faster (no dual-memory sync overhead)
- LLM: No change (same logic)

## Timeline

**Total Estimated Time**: 4-5 days

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 1: Preparation | 1-2 days | 1-2 days |
| Phase 2: LLM Migration | 0.5 day | 1.5-2.5 days |
| Phase 3: Basic Agent | 1 day | 2.5-3.5 days |
| Phase 4: Deep Agent | 1 day | 3.5-4.5 days |
| Phase 5: Commands | 0.5 day | 4-5 days |
| Phase 6: Cleanup | 0.5 day | 4.5-5.5 days |

**Buffer**: +1 day for unexpected issues

**Total**: 5-6 days

## Success Criteria

### Functional
- [ ] LLM mode saves and loads history correctly
- [ ] Basic Agent preserves history after engine switch
- [ ] Deep Agent HITL works as before
- [ ] All three modes have isolated storage directories
- [ ] Session commands work across modes
- [ ] `/restore` preserves selection after `/switch`

### Code Quality
- [ ] All tests pass
- [ ] No dead code remains
- [ ] Documentation updated
- [ ] Code review approved

### Performance
- [ ] No regression in response time
- [ ] Memory usage within acceptable range
- [ ] File I/O operations not increased

## Rollback Plan

If critical issues arise:

1. **Immediate**: Revert to previous git commit
2. **Data**: Restore backup of `data/` directory
3. **Services**: Restart services to clear in-memory state
4. **Verify**: Run smoke tests to confirm rollback success

**Note**: Session files are backward compatible - no data loss from rollback.

## Next Steps

1. Review this plan with team
2. Schedule implementation window
3. Create backup of `data/` directory
4. Begin Phase 1 (create new modules)
5. Test incrementally after each phase
6. Deploy to production after full testing

## Questions?

For more details:
- Architecture questions → [architecture.md](./architecture.md)
- Implementation questions → [refactor-code.md](./refactor-code.md)
- Integration questions → [integration.md](./integration.md)
