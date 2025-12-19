# Testing Guide for Memory Module Refactoring

## Overview

This document outlines unit testing strategies and key test cases for the memory module refactoring. The goal is to ensure:
- New implementation fixes existing bugs
- Deep Agent HITL functionality remains intact
- No regressions in session management

---

## Test Structure

### Directory Layout

```
tests/unit/memory/
├── test_llm_memory.py                # LLM mode tests
├── test_basic_agent_checkpointer.py  # Basic Agent tests
├── test_deep_agent_checkpointer.py   # Deep Agent tests
├── test_session_manager.py           # Session management tests
└── fixtures/
    ├── mock_storage.py               # Storage mocks
    └── sample_sessions.py            # Test data
```

---

## Critical Test Cases

### 1. Overwrite Bug Prevention (MUST PASS)

**Purpose**: Verify that BasicAgentCheckpointer does NOT overwrite existing history

**File**: `tests/unit/memory/test_basic_agent_checkpointer.py`

```python
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from src.components.shared.memory import BasicAgentCheckpointer

def test_history_not_overwritten_after_restore():
    """
    Test Case: Overwrite Bug Prevention

    Scenario:
    1. Session has 6 historical messages
    2. User restores session
    3. User sends new message

    Expected:
    - All 6 historical messages preserved
    - New messages appended (total 8 messages)

    Bug Behavior (old implementation):
    - Only 2 new messages remain
    - 6 historical messages deleted
    """
    # Setup
    checkpointer = BasicAgentCheckpointer(storage_dir="data/test/basicagent")
    session_id = "test_session_001"

    # Simulate existing history (6 messages)
    existing_messages = [
        HumanMessage(content="Question 1"),
        AIMessage(content="Answer 1"),
        HumanMessage(content="Question 2"),
        AIMessage(content="Answer 2"),
        HumanMessage(content="Question 3"),
        AIMessage(content="Answer 3"),
    ]
    checkpointer.storage.save_session(session_id, existing_messages)

    # Simulate restoration and new message
    config = {
        "configurable": {
            "thread_id": session_id,
            "checkpoint_ns": "",
            "checkpoint_id": "1"
        }
    }

    # Agent processes new turn (only has current turn in checkpoint)
    new_checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="Question 4"),
                AIMessage(content="Answer 4"),
            ]
        }
    }

    # Save checkpoint (this should MERGE, not OVERWRITE)
    checkpointer.put(config, new_checkpoint, {}, {})

    # Verify
    loaded_messages = checkpointer.storage.load_session(session_id)

    # CRITICAL: All 8 messages should exist
    assert len(loaded_messages) == 8, f"Expected 8 messages, got {len(loaded_messages)}"

    # Verify order
    assert loaded_messages[0].content == "Question 1"
    assert loaded_messages[5].content == "Answer 3"
    assert loaded_messages[6].content == "Question 4"
    assert loaded_messages[7].content == "Answer 4"
```

**Validation**:
- Run this test against OLD implementation: MUST FAIL (only 2 messages)
- Run this test against NEW implementation: MUST PASS (8 messages)

---

### 2. HITL Functionality Preservation (CRITICAL)

**Purpose**: Verify Deep Agent can recover from interrupts

**File**: `tests/unit/memory/test_deep_agent_checkpointer.py`

```python
import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from src.components.shared.memory import DeepAgentCheckpointer

def test_hitl_state_recovery():
    """
    Test Case: HITL State Recovery

    Scenario:
    1. Deep Agent starts execution with tool call
    2. Waits for user approval (interrupt)
    3. User approves
    4. Agent resumes from interrupt point

    Expected:
    - Runtime checkpoint contains tool call state
    - persist_from_runtime() saves Human/AI messages only
    - ToolMessage filtered out from persistent storage
    """
    # Setup
    deep_checkpointer = DeepAgentCheckpointer(storage_dir="data/test/deepagent")
    runtime_checkpointer = MemorySaver()  # HITL runtime
    session_id = "test_hitl_001"

    # Simulate agent execution with interrupt
    config = {
        "configurable": {
            "thread_id": session_id,
            "checkpoint_ns": ""
        }
    }

    # Agent state before interrupt (includes ToolMessage)
    agent_state = {
        "messages": [
            HumanMessage(content="Search for Python tutorials"),
            AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}}]),
            ToolMessage(content="Found 10 results", tool_call_id="call_123"),
        ]
    }

    # Save to runtime checkpointer (for resume)
    runtime_checkpoint = {
        "channel_values": agent_state,
        "ts": "2024-01-01T00:00:00Z"
    }
    runtime_checkpointer.put(config, runtime_checkpoint, {}, {})

    # Persist to storage (should filter ToolMessage)
    success = deep_checkpointer.persist_from_runtime(
        session_id=session_id,
        runtime_checkpointer=runtime_checkpointer,
        runtime_config=config,
        agent_state=agent_state
    )

    assert success is True

    # Verify persistent storage (no ToolMessage)
    persisted = deep_checkpointer.storage.load_session(session_id)
    assert len(persisted) == 2  # Only HumanMessage + AIMessage
    assert isinstance(persisted[0], HumanMessage)
    assert isinstance(persisted[1], AIMessage)

    # Verify runtime checkpoint still has all messages (for resume)
    runtime_tuple = runtime_checkpointer.get_tuple(config)
    runtime_messages = runtime_tuple.checkpoint["channel_values"]["messages"]
    assert len(runtime_messages) == 3  # All 3 including ToolMessage


def test_enhance_runtime_input_loads_history():
    """
    Test Case: History Injection

    Scenario:
    1. Session has 10 historical messages
    2. User sends new query
    3. enhance_runtime_input() injects last N messages

    Expected:
    - Returns last N messages + new query
    - Messages loaded from SessionStorage
    """
    # Setup
    checkpointer = DeepAgentCheckpointer(storage_dir="data/test/deepagent")
    session_id = "test_history_001"

    # Simulate existing history (10 messages)
    history = []
    for i in range(5):
        history.extend([
            HumanMessage(content=f"Question {i+1}"),
            AIMessage(content=f"Answer {i+1}")
        ])
    checkpointer.storage.save_session(session_id, history)

    # Enhance input with history (max 6 messages)
    result = checkpointer.enhance_runtime_input(
        session_id=session_id,
        user_query="Question 6",
        max_history=6
    )

    # Verify
    messages = result["messages"]
    assert len(messages) == 7  # 6 history + 1 new query
    assert messages[0].content == "Answer 3"  # Last 6 from history
    assert messages[6].content == "Question 6"  # New query
```

---

### 3. Session Isolation Test

**Purpose**: Verify each mode has independent storage

**File**: `tests/unit/memory/test_session_manager.py`

```python
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from src.components.shared.memory import (
    LLMMemory,
    BasicAgentCheckpointer,
    DeepAgentCheckpointer,
    SessionManager
)

def test_mode_storage_isolation():
    """
    Test Case: Mode Isolation

    Scenario:
    1. Same session_id used in all three modes
    2. Each mode saves different messages

    Expected:
    - Three separate files created
    - No cross-mode conflicts
    """
    session_id = "shared_id_001"

    # LLM mode
    llm_memory = LLMMemory(storage_dir="data/test/llm")
    llm_memory.add_conversation(session_id, "LLM question", "LLM answer")

    # Basic Agent mode
    basic_checkpointer = BasicAgentCheckpointer(storage_dir="data/test/basicagent")
    basic_config = {"configurable": {"thread_id": session_id}}
    basic_checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="Basic question"),
                AIMessage(content="Basic answer")
            ]
        }
    }
    basic_checkpointer.put(basic_config, basic_checkpoint, {}, {})

    # Deep Agent mode
    deep_checkpointer = DeepAgentCheckpointer(storage_dir="data/test/deepagent")
    deep_checkpointer.storage.save_session(session_id, [
        HumanMessage(content="Deep question"),
        AIMessage(content="Deep answer")
    ])

    # Verify isolation
    llm_messages = llm_memory.get_history(session_id)
    basic_messages = basic_checkpointer.storage.load_session(session_id)
    deep_messages = deep_checkpointer.storage.load_session(session_id)

    assert len(llm_messages) == 2
    assert len(basic_messages) == 2
    assert len(deep_messages) == 2

    # Each mode has different content
    assert llm_messages[0].content == "LLM question"
    assert basic_messages[0].content == "Basic question"
    assert deep_messages[0].content == "Deep question"


def test_session_manager_cross_mode_queries():
    """
    Test Case: Cross-mode Session Queries

    Scenario:
    1. Create sessions in each mode
    2. Use SessionManager.list_all_sessions()

    Expected:
    - Returns grouped sessions by mode
    """
    manager = SessionManager(mode="basic")

    # Create sessions in each mode
    LLMMemory("data/test/llm").add_conversation("llm_001", "q", "a")
    BasicAgentCheckpointer("data/test/basicagent").storage.save_session("basic_001", [])
    DeepAgentCheckpointer("data/test/deepagent").storage.save_session("deep_001", [])

    # Query all sessions
    all_sessions = manager.list_all_sessions()

    assert "llm" in all_sessions
    assert "basic" in all_sessions
    assert "deep" in all_sessions

    assert len(all_sessions["llm"]) >= 1
    assert len(all_sessions["basic"]) >= 1
    assert len(all_sessions["deep"]) >= 1
```

---

### 4. History Preservation Across Engine Switch

**Purpose**: Verify session remains available after /switch command

**File**: `tests/unit/memory/test_basic_agent_checkpointer.py`

```python
def test_history_preserved_after_engine_switch():
    """
    Test Case: Engine Switch Preservation

    Scenario:
    1. User restores session with history
    2. User switches from gpt-4o to claude-3
    3. User sends new message

    Expected:
    - History remains loaded
    - New message appends to history

    Bug Behavior (old):
    - /switch command resets session to most recent
    - Restored session_id lost
    """
    checkpointer = BasicAgentCheckpointer(storage_dir="data/test/basicagent")

    # Simulate restored session
    restored_id = "user_20240101_abc123"
    history = [
        HumanMessage(content="Restored message 1"),
        AIMessage(content="Restored answer 1")
    ]
    checkpointer.storage.save_session(restored_id, history)

    # Simulate engine switch (should NOT change session_id)
    # This test verifies checkpointer behavior, not command logic

    # Add new message to same session
    config = {"configurable": {"thread_id": restored_id}}
    new_checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="After switch message"),
                AIMessage(content="After switch answer")
            ]
        }
    }
    checkpointer.put(config, new_checkpoint, {}, {})

    # Verify
    loaded = checkpointer.storage.load_session(restored_id)
    assert len(loaded) == 4
    assert loaded[0].content == "Restored message 1"
    assert loaded[2].content == "After switch message"
```

---

## Test Fixtures

### Mock Storage

**File**: `tests/unit/memory/fixtures/mock_storage.py`

```python
from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage

class MockSessionStorage:
    """In-memory storage for testing"""

    def __init__(self, storage_dir: str = ""):
        self.sessions: Dict[str, List[BaseMessage]] = {}
        self.metadata: Dict[str, Dict] = {}
        self.storage_dir = storage_dir

    def save_session(
        self,
        session_id: str,
        messages: List[BaseMessage],
        metadata: Optional[Dict] = None
    ) -> None:
        self.sessions[session_id] = messages
        if metadata:
            self.metadata[session_id] = metadata

    def load_session(self, session_id: str) -> Optional[List[BaseMessage]]:
        return self.sessions.get(session_id)

    def session_exists(self, session_id: str) -> bool:
        return session_id in self.sessions

    def list_sessions(self) -> List[Dict]:
        return [
            {"session_id": sid, "message_count": len(msgs)}
            for sid, msgs in self.sessions.items()
        ]

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
```

---

## Integration Tests

### End-to-End Workflow

**File**: `tests/integration/test_memory_workflow.py`

```python
import pytest
from src.application.services.agent.basic.conversation import BasicAgentConversation
from src.components.shared.memory import BasicAgentCheckpointer

@pytest.mark.integration
def test_basic_agent_full_workflow():
    """
    Integration Test: Full Basic Agent Workflow

    Workflow:
    1. Start new session
    2. Send 3 messages
    3. Restore session
    4. Send 2 more messages
    5. Verify all 5 messages preserved
    """
    # This test requires running actual agent
    # Use mock LLM to avoid API costs

    # Step 1: Start new session
    service = BasicAgentConversation(
        llm_provider="mock",
        model_name="mock-gpt-4o"
    )

    session_id = service.create_new_session()

    # Step 2: Send 3 messages
    service.process_message(session_id, "Question 1")
    service.process_message(session_id, "Question 2")
    service.process_message(session_id, "Question 3")

    # Step 3: Restore session (simulate restart)
    service2 = BasicAgentConversation(
        llm_provider="mock",
        model_name="mock-gpt-4o"
    )
    service2.restore_session(session_id)

    # Step 4: Send 2 more messages
    service2.process_message(session_id, "Question 4")
    service2.process_message(session_id, "Question 5")

    # Step 5: Verify
    checkpointer = BasicAgentCheckpointer()
    messages = checkpointer.storage.load_session(session_id)

    # 5 questions + 5 answers = 10 messages
    assert len(messages) == 10
```

---

## Performance Tests

### Message Deduplication Performance

**File**: `tests/performance/test_deduplication.py`

```python
import pytest
import time
from langchain_core.messages import HumanMessage, AIMessage
from src.components.shared.memory import DeepAgentCheckpointer

def test_deduplication_performance():
    """
    Performance Test: Deduplication with Large History

    Scenario:
    - Session has 1000 messages
    - Add 10 new messages (5 duplicates)
    - Measure deduplication time

    Expected:
    - Deduplication completes in < 100ms
    """
    checkpointer = DeepAgentCheckpointer()

    # Generate 1000 messages
    large_history = []
    for i in range(500):
        large_history.extend([
            HumanMessage(content=f"Question {i}"),
            AIMessage(content=f"Answer {i}")
        ])

    # Add 10 new (5 duplicates)
    new_messages = large_history[-10:] + [
        HumanMessage(content="New question"),
        AIMessage(content="New answer")
    ]

    # Benchmark
    start = time.time()
    result = checkpointer._deduplicate_messages(large_history + new_messages)
    duration = (time.time() - start) * 1000  # ms

    # Verify
    assert len(result) == 1002  # 1000 + 2 new
    assert duration < 100, f"Deduplication took {duration}ms (expected < 100ms)"
```

---

## Test Execution

### Run All Tests

```bash
# Unit tests only
pytest tests/unit/memory/ -v

# Integration tests
pytest tests/integration/ -v --integration

# Performance tests
pytest tests/performance/ -v

# Full test suite
pytest tests/ -v --cov=src/components/shared/memory
```

### Test Coverage Requirements

Minimum coverage thresholds:

- `llm_memory.py`: 90%
- `basic_agent_checkpointer.py`: 95% (critical bug fix)
- `deep_agent_checkpointer.py`: 90% (complex HITL logic)
- `session_manager.py`: 85%

---

## Regression Test Suite

### Pre-Refactoring Baseline

Before refactoring, run existing tests to establish baseline:

```bash
# Capture baseline (expected to have failures)
pytest tests/unit/memory-storage/ -v > baseline_results.txt

# Expected failures:
# - test_session_commands.py::test_restore_then_switch (Bug #1)
# - test_basic_agent_memory.py::test_history_preservation (Bug #2)
```

### Post-Refactoring Validation

After refactoring, ALL tests must pass:

```bash
# Run same test suite
pytest tests/unit/memory/ -v > refactored_results.txt

# Required: Zero failures
# Required: All new test cases pass
```

---

## Summary

### Critical Test Cases (MUST PASS)

1. **test_history_not_overwritten_after_restore()** - Fixes Bug #2
2. **test_hitl_state_recovery()** - Preserves Deep Agent functionality
3. **test_mode_storage_isolation()** - Prevents conflicts
4. **test_history_preserved_after_engine_switch()** - Fixes Bug #1

### Test Execution Order

1. Run unit tests for each module independently
2. Run integration tests for workflow validation
3. Run performance tests for benchmarking
4. Run regression suite to ensure no new bugs

### Success Criteria

- All critical test cases pass
- Test coverage >= 90% for new modules
- No regressions in existing functionality
- Performance within acceptable thresholds (<100ms for deduplication)
