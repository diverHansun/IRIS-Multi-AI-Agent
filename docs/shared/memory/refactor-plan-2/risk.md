# Refactoring Risk Analysis and Mitigation

## Risk Classification

Risks are classified by **Impact** (Low/Medium/High) and **Probability** (Low/Medium/High).

---

## Critical Risks (High Impact)

### R1: Deep Agent HITL Functionality Break

**Impact**: High - HITL is core feature for Deep Agent
**Probability**: Medium - Complex integration with MemorySaver

**Description**:
During refactoring, the Deep Agent's HITL (Human-in-the-Loop) capability might break if:
- `enhance_runtime_input()` logic is incorrectly integrated
- `persist_from_runtime()` loses message filtering logic
- Runtime checkpointer state management is disrupted

**Symptoms**:
- HITL approval prompts don't appear
- Agent crashes when resuming from interrupt
- State recovery fails after approval/rejection
- ToolMessages leak into persistent storage

**Root Causes**:
1. `MemorySyncAdapter` logic not fully preserved in `DeepAgentCheckpointer`
2. `_flatten_messages()` or `_deduplicate_messages()` logic lost
3. Runtime checkpointer not properly initialized

**Mitigation**:

**Pre-Implementation**:
- Document all HITL-related code paths in `memory_sync.py`
- Create comprehensive HITL test cases before refactoring
- Review Deep Agent's interrupt handling logic

**During Implementation**:
- Copy `MemorySyncAdapter` methods verbatim to `DeepAgentCheckpointer`
- Preserve all helper methods (`_flatten_messages`, `_deduplicate_messages`)
- Test HITL after each incremental change

**Verification**:
```python
# Test HITL approval
1. Trigger tool requiring approval (e.g., shell command)
2. Verify approval prompt appears
3. Approve and verify execution continues
4. Check data/deepagent/sessions/*.json - no ToolMessages

# Test HITL rejection
1. Trigger approval prompt
2. Reject
3. Verify agent handles rejection gracefully
```

**Rollback Trigger**:
- If HITL tests fail after Deep Agent migration
- If state recovery fails in any HITL scenario

---

### R2: Data Loss During Migration

**Impact**: High - User data is irreplaceable
**Probability**: Low - With proper backup procedures

**Description**:
Session files might be lost or corrupted during:
- Directory reorganization (`data/llm_basicagent/` → `data/llm/`, `data/basicagent/`)
- File format changes (unlikely, but possible)
- Code bugs in new checkpointers

**Scenarios**:
1. **Accidental deletion**: Moving files between directories
2. **Overwrite bug persists**: New checkpointer has same bug as old
3. **Corruption**: File I/O errors during migration

**Mitigation**:

**Pre-Implementation**:
```bash
# Mandatory backup before any code changes
cp -r data/ data_backup_$(date +%Y%m%d_%H%M%S)/

# Or use git-ignored backup directory
mkdir -p .backups
cp -r data/ .backups/data_$(date +%Y%m%d_%H%M%S)/
```

**During Implementation**:
- Implement file copy (not move) for directory reorganization
- Verify checksums after copying files
- Keep old files until verification complete

**Migration Script**:
```python
# scripts/migrate_sessions.py

import shutil
from pathlib import Path

def migrate_sessions():
    """Safely migrate session files to new directory structure."""

    old_dir = Path("data/llm_basicagent/sessions")
    llm_dir = Path("data/llm/sessions")
    basic_dir = Path("data/basicagent/sessions")

    # Create new directories
    llm_dir.mkdir(parents=True, exist_ok=True)
    basic_dir.mkdir(parents=True, exist_ok=True)

    # Copy (not move) files
    for session_file in old_dir.glob("*.json"):
        # Strategy: Copy to both (user decides which to keep)
        shutil.copy2(session_file, llm_dir / session_file.name)
        shutil.copy2(session_file, basic_dir / session_file.name)
        print(f"Copied {session_file.name} to llm/ and basicagent/")

    print("\nMigration complete. Old files preserved in llm_basicagent/")
    print("Verify new directories before deleting old files.")

# Only delete old files after manual verification
# rm -rf data/llm_basicagent/  # DO NOT automate this
```

**Verification**:
```bash
# After migration, verify file counts
ls data/llm_basicagent/sessions/*.json | wc -l
ls data/llm/sessions/*.json | wc -l
ls data/basicagent/sessions/*.json | wc -l

# Verify file integrity
md5sum data/llm_basicagent/sessions/user_*.json > old_checksums.txt
md5sum data/llm/sessions/user_*.json > new_llm_checksums.txt
diff old_checksums.txt new_llm_checksums.txt  # Should be identical
```

**Rollback Trigger**:
- Any file corruption detected
- File count mismatch after migration
- Checksum verification failure

---

### R3: Basic Agent History Overwrite Bug Persists

**Impact**: High - Original bug not fixed
**Probability**: Low-Medium - If checkpointer implementation is incorrect

**Description**:
The new `BasicAgentCheckpointer` might have the same overwrite bug if:
- `get_tuple()` doesn't load existing history correctly
- `put()` uses overwrite instead of merge strategy
- SessionStorage API is misused

**Symptoms**:
- After `/restore` + `/switch` + send message, only 2 messages in file (same as old bug)
- History appears empty after engine switch
- Old messages disappear after new conversation

**Root Cause**:
```python
# WRONG IMPLEMENTATION (reproduces bug)
def put(self, config, checkpoint, metadata, new_versions):
    messages = checkpoint["channel_values"]["messages"]
    # BUG: Directly saves without loading existing
    self.storage.save_session(thread_id, messages)  # Overwrites!

# CORRECT IMPLEMENTATION
def put(self, config, checkpoint, metadata, new_versions):
    messages = checkpoint["channel_values"]["messages"]

    # Load existing first
    existing = self.storage.load_session(thread_id) or []

    # Merge strategy (deduplicate)
    all_messages = existing + messages
    deduplicated = self._deduplicate(all_messages)

    # Save merged
    self.storage.save_session(thread_id, deduplicated)
```

**Mitigation**:

**Pre-Implementation**:
- Write unit test specifically for overwrite bug scenario
- Test must reproduce the bug with old code

**Test Case**:
```python
def test_basic_agent_no_overwrite_after_engine_switch():
    """Verify bug is fixed: history preserved after engine switch."""

    # Setup
    checkpointer = BasicAgentCheckpointer("test_data")
    session_id = "test_session"

    # Simulate existing history (6 messages)
    existing = [
        HumanMessage("Q1"), AIMessage("A1"),
        HumanMessage("Q2"), AIMessage("A2"),
        HumanMessage("Q3"), AIMessage("A3"),
    ]
    checkpointer.storage.save_session(session_id, existing)

    # Simulate new conversation (2 messages)
    new_messages = [
        HumanMessage("Q4"), AIMessage("A4"),
    ]

    # Simulate LangGraph calling put()
    checkpoint = {
        "id": "checkpoint_1",
        "channel_values": {"messages": new_messages},
        "channel_versions": {"messages": 2},
        "versions_seen": {},
    }
    config = {"configurable": {"thread_id": session_id}}

    checkpointer.put(config, checkpoint, {}, {"messages": 2})

    # Verify: Should have 8 messages (6 old + 2 new)
    loaded = checkpointer.storage.load_session(session_id)
    assert len(loaded) == 8, f"Expected 8 messages, got {len(loaded)}"
    assert loaded[0].content == "Q1"  # Old messages preserved
    assert loaded[-1].content == "A4"  # New messages appended
```

**Verification**:
- Run test with old code → Should fail (confirms bug)
- Implement `BasicAgentCheckpointer`
- Run test with new code → Should pass (confirms fix)

**Rollback Trigger**:
- If test fails with new checkpointer
- If manual testing shows history still overwrites

---

## High-Probability Risks (Medium Impact)

### R4: Import Errors After File Reorganization

**Impact**: Medium - Breaks functionality but easy to detect
**Probability**: High - Many files import memory modules

**Description**:
After deleting `global_memory.py` and `memory_sync.py`, imports will break in:
- LLM service
- Basic Agent service
- Deep Agent service
- CLI commands
- Session management

**Affected Files** (Estimated 10-15 files):
```
src/application/services/llm/conversation.py
src/application/services/agent/basic/conversation.py
src/application/services/agent/deep/streaming/conversation.py
src/application/commands/shared/session_commands.py
src/application/commands/engine_commands.py
src/application/cli/main.py
... and more
```

**Symptoms**:
```python
ImportError: cannot import name 'GlobalMemoryManager' from 'src.components.shared.memory'
ImportError: cannot import name 'MemorySyncAdapter' from 'src.components.shared.memory'
```

**Mitigation**:

**Pre-Implementation**:
```bash
# Find all import statements
grep -r "from.*memory import" src/ | grep -E "(GlobalMemoryManager|MemorySyncAdapter)"

# Expected files to update:
# src/application/services/llm/conversation.py
# src/application/services/agent/basic/conversation.py
# src/application/services/agent/deep/streaming/conversation.py
# src/application/commands/shared/session_commands.py
# src/application/commands/engine_commands.py
# src/application/cli/main.py
```

**During Implementation**:
- Update imports incrementally (one service at a time)
- Use Python's `-m py_compile` to check syntax before running

**Verification**:
```bash
# Check all Python files compile
find src -name "*.py" -exec python -m py_compile {} \;

# Check no references to old modules
grep -r "GlobalMemoryManager" src/  # Should only find in migration notes
grep -r "MemorySyncAdapter" src/    # Should only find in migration notes
```

**Quick Fix**:
- Keep old files temporarily with deprecation warnings
- Gradual migration: old and new modules coexist

---

### R5: Session ID Conflicts After Mode Switch

**Impact**: Medium - User confusion, wrong history loaded
**Probability**: Medium - If `/switch` logic not updated correctly

**Description**:
User switches from LLM to Basic Agent:
- Same `session_id` exists in both `data/llm/` and `data/basicagent/`
- Which one to load?
- User expects continuity but gets isolated history

**Scenario**:
```
1. User in LLM mode: session_id = "user_20251219_123456"
2. Chat for 5 turns → saved to data/llm/sessions/user_20251219_123456.json
3. /switch agent
4. System loads data/basicagent/sessions/ (empty, no such session)
5. User asks "what did we discuss?" → Agent: "I don't recall"
```

**Mitigation**:

**Option A: Accept Isolation (Recommended for initial implementation)**
```python
# In /switch command
def switch_engine(ctx, new_mode):
    ctx.session_manager.mode = new_mode

    # Check if current session exists in new mode
    if ctx.session_id and ctx.session_manager.session_exists(ctx.session_id, mode=new_mode):
        # Keep current session
        pass
    else:
        # Create new session or load most recent
        ctx.console.print(
            f"[yellow]Note: Starting fresh in {new_mode} mode. "
            f"Previous conversation is in {ctx.current_mode} mode.[/]"
        )
        recent = ctx.session_manager.get_most_recent_session(mode=new_mode)
        ctx.session_id = recent["session_id"] if recent else ctx.session_manager.create_new_session()
```

**Option B: Copy Session on Switch (Future enhancement)**
```python
# Add --copy flag to /switch
def switch_engine(ctx, new_mode, copy_session=False):
    if copy_session and ctx.session_id:
        # Copy current session to new mode's directory
        old_dir = ctx.session_manager.storage_dirs[ctx.current_mode]
        new_dir = ctx.session_manager.storage_dirs[new_mode]

        old_file = f"{old_dir}/{ctx.session_id}.json"
        new_file = f"{new_dir}/{ctx.session_id}.json"

        shutil.copy2(old_file, new_file)
        ctx.console.print(f"[green]Session copied to {new_mode} mode[/]")
```

**Verification**:
```python
# Test mode switch behavior
1. LLM mode: chat 3 turns, note session_id
2. /switch agent
3. Check ctx.session_id:
   - Option A: Different session_id (new)
   - Option B: Same session_id (copied)
4. /sessions: Should show both LLM and Basic sessions
```

---

### R6: Performance Regression in SessionStorage

**Impact**: Medium - Slower response times
**Probability**: Low - SessionStorage unchanged

**Description**:
If new checkpointers call `load_session()` / `save_session()` more frequently than old code:
- More file I/O operations
- Slower response times
- Disk I/O bottleneck

**Scenarios**:
1. `BasicAgentCheckpointer.put()` loads history on every call
2. No caching in checkpointers (old code had in-memory cache in GlobalMemoryManager)

**Mitigation**:

**Measurement**:
```python
# Add performance logging
import time

class BasicAgentCheckpointer:
    def put(self, config, checkpoint, metadata, new_versions):
        start = time.time()
        # ... implementation ...
        elapsed = time.time() - start
        if elapsed > 0.1:  # 100ms threshold
            logger.warning(f"Slow put operation: {elapsed:.2f}s")
```

**Optimization** (if needed):
```python
# Add simple in-memory cache
class BasicAgentCheckpointer:
    def __init__(self, storage_dir):
        self.storage = SessionStorage(storage_dir)
        self._cache = {}  # session_id -> messages
        self._cache_ttl = {}  # session_id -> timestamp

    def get_tuple(self, config):
        thread_id = config["configurable"]["thread_id"]

        # Check cache (5 second TTL)
        if thread_id in self._cache:
            if time.time() - self._cache_ttl[thread_id] < 5:
                messages = self._cache[thread_id]
                # Return cached data

        # Load from storage
        messages = self.storage.load_session(thread_id)

        # Update cache
        self._cache[thread_id] = messages
        self._cache_ttl[thread_id] = time.time()

        # Return checkpoint
```

**Verification**:
```bash
# Benchmark before and after
time python -c "
from src.application.services.agent.basic.conversation import handle_agent_query
# ... run query ...
"

# Compare response times
# Before: X seconds
# After: Should be similar (±10%)
```

---

## Low-Impact Risks

### R7: Documentation Outdated

**Impact**: Low - Does not affect functionality
**Probability**: High - Many docs reference old architecture

**Mitigation**:
- Update architecture docs after each phase
- Mark old docs as deprecated
- Add migration guide

---

### R8: Test Suite Breakage

**Impact**: Low - Tests can be updated
**Probability**: High - Many tests use GlobalMemoryManager

**Affected Tests**:
- `tests/unit/memory-storage/test_session_commands.py` (uses GlobalMemoryManager)
- `tests/unit/test_dual_checkpointer.py` (uses UnifiedCheckpointer)

**Mitigation**:
- Update tests in parallel with code changes
- Keep old test files as reference

---

## Risk Matrix

| Risk | Impact | Probability | Priority | Mitigation Status |
|------|--------|-------------|----------|-------------------|
| R1: HITL Break | High | Medium | Critical | Detailed plan ready |
| R2: Data Loss | High | Low | Critical | Backup procedure mandatory |
| R3: Overwrite Bug | High | Medium | Critical | Unit test prepared |
| R4: Import Errors | Medium | High | High | File list ready |
| R5: Session Conflicts | Medium | Medium | High | Two options prepared |
| R6: Performance | Medium | Low | Medium | Monitoring plan ready |
| R7: Docs Outdated | Low | High | Low | Update checklist |
| R8: Tests Break | Low | High | Low | Parallel update |

---

## Pre-Flight Checklist

Before starting refactoring:

**Mandatory**:
- [ ] Backup `data/` directory
- [ ] Create git branch for refactoring
- [ ] Review HITL test cases
- [ ] Identify all import sites for GlobalMemoryManager and MemorySyncAdapter
- [ ] Write unit test for overwrite bug scenario

**Recommended**:
- [ ] Benchmark current performance (baseline)
- [ ] Document current HITL flow in Deep Agent
- [ ] Create rollback plan
- [ ] Set up automated test run after each phase

**Optional**:
- [ ] Set up monitoring for file I/O operations
- [ ] Create session file integrity checker
- [ ] Prepare communication plan for users (if production)

---

## Emergency Rollback Procedures

### Immediate Rollback (< 5 minutes)

**Symptoms**: Critical failure (HITL broken, data loss, import errors everywhere)

**Steps**:
```bash
# 1. Revert code
git reset --hard HEAD~N  # N = number of commits to revert

# 2. Restore data
rm -rf data/
cp -r data_backup_YYYYMMDD_HHMMSS/ data/

# 3. Restart services
python main.py  # or your startup command

# 4. Verify
# Test LLM mode, Basic Agent, Deep Agent
```

### Partial Rollback (Specific Module)

**Symptoms**: One mode broken, others OK

**LLM Mode Only**:
```bash
# Revert LLM mode changes
git checkout HEAD -- src/application/services/llm/
git checkout HEAD -- src/components/shared/memory/llm_memory.py

# Keep other changes
# Restart and test
```

**Similar for Basic or Deep modes**

---

## Monitoring and Detection

### Early Warning Signs

**During Development**:
- Unit tests failing
- Import errors when running application
- File count mismatch in `data/` directories

**After Deployment**:
- User reports "history disappeared"
- HITL prompts not appearing
- Error logs showing `FileNotFoundError`

### Health Checks

**Post-Deployment Checks** (run after each phase):
```python
# scripts/health_check.py

def check_memory_system():
    """Health check for memory system."""

    checks = []

    # 1. All directories exist
    dirs = ["data/llm/sessions", "data/basicagent/sessions", "data/deepagent/sessions"]
    for dir in dirs:
        exists = Path(dir).exists()
        checks.append(("Directory exists: " + dir, exists))

    # 2. Session files readable
    for dir in dirs:
        for session_file in Path(dir).glob("*.json"):
            try:
                with open(session_file) as f:
                    json.load(f)
                checks.append((f"Valid JSON: {session_file.name}", True))
            except:
                checks.append((f"Valid JSON: {session_file.name}", False))

    # 3. Imports work
    try:
        from src.components.shared.memory import (
            LLMMemory, BasicAgentCheckpointer, DeepAgentCheckpointer, SessionManager
        )
        checks.append(("Imports successful", True))
    except:
        checks.append(("Imports successful", False))

    # Print results
    for check_name, passed in checks:
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {check_name}")

    return all(passed for _, passed in checks)
```

---

## Summary

**Critical Risks** (must mitigate):
1. HITL functionality break → Preserve all MemorySyncAdapter logic
2. Data loss → Mandatory backup before any changes
3. Overwrite bug persists → Write unit test first

**High-Probability Risks** (prepare for):
4. Import errors → Find all import sites beforehand
5. Session conflicts → Decide on isolation strategy
6. Performance regression → Monitor and optimize if needed

**Low-Impact Risks** (monitor):
7. Documentation → Update incrementally
8. Tests → Update in parallel

**Key Success Factors**:
- Incremental migration (one mode at a time)
- Comprehensive testing after each phase
- Keep backup and rollback plan ready
- Monitor health checks continuously
