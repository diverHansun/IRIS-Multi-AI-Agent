"""
Test session management commands.

Tests /sessions, /cleanup, /new, /clear, /restore, /delete_session commands.
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pytest

pytest.skip("Legacy GlobalMemoryManager tests skipped after memory refactor", allow_module_level=True)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'src'))

from components.shared.memory.global_memory import GlobalMemoryManager
from components.shared.memory.session_manager import SessionManager
from components.shared.storage.session_storage import SessionStorage
from langchain_core.messages import HumanMessage, AIMessage


class MockContext:
    """Mock CLI context for testing."""
    def __init__(self, mode="basic", test_name="default"):
        self.mode = mode
        self.test_name = test_name
        self.test_dir = Path(f"tests/unit/memory-storage/test_data_{mode}_{test_name}")
        
        # Clean up test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize memory system
        self.global_memory = GlobalMemoryManager(
            storage_dir=str(self.test_dir),
            agent_mode=mode,
            max_messages=50
        )
        self.session_manager = SessionManager(self.global_memory, mode=mode)
        self.session_id = None
        
    def cleanup(self):
        """Clean up test data."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)


def test_new_session_command():
    """Test /new command."""
    print("\n=== Test: /new command ===")
    
    ctx = MockContext("basic", "new_session")
    
    # Create first session
    session1 = ctx.session_manager.create_new_session()
    assert session1.startswith("user_"), f"Session ID should start with 'user_': {session1}"
    print(f"[OK] Created session 1: {session1}")
    
    # Create second session
    session2 = ctx.session_manager.create_new_session()
    assert session2 != session1, "New session should have different ID"
    print(f"[OK] Created session 2: {session2}")
    
    # Verify session files exist
    storage = ctx.global_memory.storage
    assert storage.session_exists(session1), f"Session 1 should exist: {session1}"
    assert storage.session_exists(session2), f"Session 2 should exist: {session2}"
    print(f"[OK] Both sessions exist in storage")
    
    ctx.cleanup()
    print("[PASS] Test passed: /new command")


def test_list_sessions_command():
    """Test /sessions command."""
    print("\n=== Test: /sessions command ===")
    
    ctx = MockContext("basic", "list_sessions")
    
    # Create multiple sessions with messages
    sessions = []
    for i in range(3):
        session_id = ctx.session_manager.create_new_session()
        sessions.append(session_id)
        
        # Add messages
        messages = [
            HumanMessage(content=f"Question {i}"),
            AIMessage(content=f"Answer {i}")
        ]
        ctx.global_memory.storage.save_session(session_id, messages)
        print(f"[OK] Created session {i+1}: {session_id} with {len(messages)} messages")
    
    # List sessions
    listed_sessions = ctx.global_memory.list_sessions()
    assert len(listed_sessions) == 3, f"Should list 3 sessions, got {len(listed_sessions)}"
    print(f"[OK] Listed {len(listed_sessions)} sessions")
    
    # Verify sorting (most recent first)
    for i, session_info in enumerate(listed_sessions):
        assert "session_id" in session_info, "Session info should have session_id"
        assert "message_count" in session_info, "Session info should have message_count"
        assert "updated_at" in session_info, "Session info should have updated_at"
        print(f"  Session {i+1}: {session_info['session_id'][:20]}... ({session_info['message_count']} messages)")
    
    ctx.cleanup()
    print("[PASS] Test passed: /sessions command")


def test_clear_session_command():
    """Test /clear command."""
    print("\n=== Test: /clear command ===")
    
    ctx = MockContext("basic", "clear_session")
    
    # Create session with messages
    session_id = ctx.session_manager.create_new_session()
    messages = [
        HumanMessage(content="Question 1"),
        AIMessage(content="Answer 1"),
        HumanMessage(content="Question 2"),
        AIMessage(content="Answer 2")
    ]
    ctx.global_memory.storage.save_session(session_id, messages)
    print(f"[OK] Created session with {len(messages)} messages")
    
    # Verify messages exist
    loaded = ctx.global_memory.storage.load_session(session_id)
    assert len(loaded) == 4, f"Should have 4 messages, got {len(loaded)}"
    print(f"[OK] Verified {len(loaded)} messages in session")
    
    # Clear session
    ctx.session_manager.current_session_id = session_id
    success = ctx.session_manager.clear_current_session()
    assert success, "Clear session should succeed"
    print(f"[OK] Cleared session: {session_id}")
    
    # Verify session deleted (load_session returns None for deleted sessions)
    loaded_after = ctx.global_memory.storage.load_session(session_id)
    assert loaded_after is None, f"Should return None after clear, got {loaded_after}"
    print(f"[OK] Verified session is deleted after clear")
    
    ctx.cleanup()
    print("[PASS] Test passed: /clear command")


def test_restore_session_command():
    """Test /restore command."""
    print("\n=== Test: /restore command ===")
    
    ctx = MockContext("basic", "restore_session")
    
    # Create two sessions
    session1 = ctx.session_manager.create_new_session()
    ctx.global_memory.storage.save_session(session1, [
        HumanMessage(content="Session 1 Question"),
        AIMessage(content="Session 1 Answer")
    ])
    
    session2 = ctx.session_manager.create_new_session()
    ctx.global_memory.storage.save_session(session2, [
        HumanMessage(content="Session 2 Question"),
        AIMessage(content="Session 2 Answer")
    ])
    print(f"[OK] Created 2 sessions")
    
    # Current session is session2
    assert ctx.session_manager.current_session_id == session2
    print(f"[OK] Current session: {session2[:20]}...")
    
    # Restore session1
    success = ctx.session_manager.switch_to_session(session1)
    assert success, "Switch to session should succeed"
    assert ctx.session_manager.current_session_id == session1
    print(f"[OK] Restored session: {session1[:20]}...")
    
    # Verify messages
    messages = ctx.global_memory.storage.load_session(session1)
    assert len(messages) == 2, f"Should have 2 messages, got {len(messages)}"
    assert messages[0].content == "Session 1 Question"
    print(f"[OK] Verified session 1 messages")
    
    # Try to restore non-existent session
    success = ctx.session_manager.switch_to_session("non_existent_session")
    assert not success, "Switch to non-existent session should fail"
    print(f"[OK] Correctly rejected non-existent session")
    
    ctx.cleanup()
    print("[PASS] Test passed: /restore command")


def test_delete_session_command():
    """Test /delete_session command."""
    print("\n=== Test: /delete_session command ===")
    
    ctx = MockContext("basic", "delete_session")
    
    # Create sessions
    session1 = ctx.session_manager.create_new_session()
    session2 = ctx.session_manager.create_new_session()
    
    ctx.global_memory.storage.save_session(session1, [HumanMessage(content="Test 1")])
    ctx.global_memory.storage.save_session(session2, [HumanMessage(content="Test 2")])
    print(f"[OK] Created 2 sessions")
    
    # Verify both exist
    assert ctx.global_memory.storage.session_exists(session1)
    assert ctx.global_memory.storage.session_exists(session2)
    print(f"[OK] Verified both sessions exist")
    
    # Delete session1
    success = ctx.global_memory.storage.delete_session(session1)
    assert success, "Delete should succeed"
    print(f"[OK] Deleted session 1")
    
    # Verify session1 deleted
    assert not ctx.global_memory.storage.session_exists(session1), "Session 1 should not exist"
    assert ctx.global_memory.storage.session_exists(session2), "Session 2 should still exist"
    print(f"[OK] Verified session 1 deleted, session 2 still exists")
    
    # List sessions should only show session2
    sessions = ctx.global_memory.list_sessions()
    assert len(sessions) == 1, f"Should have 1 session, got {len(sessions)}"
    assert sessions[0]["session_id"] == session2
    print(f"[OK] List sessions shows only remaining session")
    
    ctx.cleanup()
    print("[PASS] Test passed: /delete_session command")


def test_cleanup_orphaned_sessions():
    """Test /cleanup command for orphaned sessions."""
    print("\n=== Test: /cleanup command (orphaned sessions) ===")
    
    ctx = MockContext("basic", "cleanup_orphaned")
    storage = ctx.global_memory.storage
    
    # Create normal session
    session1 = ctx.session_manager.create_new_session()
    storage.save_session(session1, [HumanMessage(content="Normal session")])
    print(f"[OK] Created normal session: {session1[:20]}...")
    
    # Create orphaned file (file without index entry)
    orphaned_file_id = "user_orphaned_file_12345678"
    orphaned_file = storage.storage_dir / f"{orphaned_file_id}.json"
    with open(orphaned_file, 'w', encoding='utf-8') as f:
        json.dump({
            "session_id": orphaned_file_id,
            "messages": [],
            "message_count": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": {}
        }, f)
    print(f"[OK] Created orphaned file: {orphaned_file_id}")
    
    # Create orphaned index entry (index without file)
    orphaned_index_id = "user_orphaned_index_87654321"
    storage.sessions_index[orphaned_index_id] = {
        "session_id": orphaned_index_id,
        "message_count": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "file_path": str(storage.storage_dir / f"{orphaned_index_id}.json")
    }
    storage._save_sessions_index()
    print(f"[OK] Created orphaned index entry: {orphaned_index_id}")
    
    # Check consistency
    consistency = storage.check_session_consistency()
    assert len(consistency["orphaned_files"]) == 1, "Should find 1 orphaned file"
    assert len(consistency["orphaned_index_entries"]) == 1, "Should find 1 orphaned index entry"
    print(f"[OK] Detected {len(consistency['orphaned_files'])} orphaned files")
    print(f"[OK] Detected {len(consistency['orphaned_index_entries'])} orphaned index entries")
    
    # Cleanup orphaned sessions
    cleanup_stats = storage.cleanup_orphaned_sessions()
    assert cleanup_stats["orphaned_files"] == 1, "Should clean 1 orphaned file"
    assert cleanup_stats["orphaned_index_entries"] == 1, "Should clean 1 orphaned index entry"
    print(f"[OK] Cleaned up {cleanup_stats['orphaned_files']} orphaned files")
    print(f"[OK] Cleaned up {cleanup_stats['orphaned_index_entries']} orphaned index entries")
    
    # Verify cleanup
    consistency_after = storage.check_session_consistency()
    assert len(consistency_after["orphaned_files"]) == 0, "Should have 0 orphaned files after cleanup"
    assert len(consistency_after["orphaned_index_entries"]) == 0, "Should have 0 orphaned index entries after cleanup"
    print(f"[OK] Verified all orphaned sessions cleaned up")
    
    # Verify normal session still exists
    assert storage.session_exists(session1), "Normal session should still exist"
    print(f"[OK] Verified normal session still exists")
    
    ctx.cleanup()
    print("[PASS] Test passed: /cleanup command (orphaned sessions)")


def test_cleanup_old_sessions():
    """Test cleanup of old sessions."""
    print("\n=== Test: cleanup old sessions ===")
    
    ctx = MockContext("basic", "cleanup_old")
    storage = ctx.global_memory.storage
    
    # Create recent session
    recent_session = ctx.session_manager.create_new_session()
    storage.save_session(recent_session, [HumanMessage(content="Recent")])
    print(f"[OK] Created recent session: {recent_session[:20]}...")
    
    # Create old session (manually set old timestamp)
    old_session = ctx.session_manager.create_new_session()
    old_date = (datetime.now() - timedelta(days=40)).isoformat()
    
    # Save with old timestamp
    storage.sessions_index[old_session]["updated_at"] = old_date
    storage._save_sessions_index()
    
    # Also update the session file
    session_file = storage.storage_dir / f"{old_session}.json"
    with open(session_file, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    session_data["updated_at"] = old_date
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Created old session (40 days old): {old_session[:20]}...")
    
    # Verify both sessions exist
    assert storage.session_exists(recent_session)
    assert storage.session_exists(old_session)
    print(f"[OK] Verified both sessions exist")
    
    # Cleanup sessions older than 30 days
    deleted_count = storage.cleanup_old_sessions(days=30)
    assert deleted_count == 1, f"Should delete 1 old session, deleted {deleted_count}"
    print(f"[OK] Cleaned up {deleted_count} old sessions")
    
    # Verify old session deleted, recent session kept
    assert storage.session_exists(recent_session), "Recent session should still exist"
    assert not storage.session_exists(old_session), "Old session should be deleted"
    print(f"[OK] Verified old session deleted, recent session kept")
    
    ctx.cleanup()
    print("[PASS] Test passed: cleanup old sessions")


def test_session_filtering():
    """Test that test sessions are filtered from list."""
    print("\n=== Test: session filtering (exclude test sessions) ===")
    
    ctx = MockContext("basic", "session_filtering")
    storage = ctx.global_memory.storage
    
    # Create user session
    user_session = ctx.session_manager.create_new_session()
    storage.save_session(user_session, [HumanMessage(content="User session")])
    print(f"[OK] Created user session: {user_session[:20]}...")
    
    # Create test session (manually)
    test_session = "test_flow_001"
    storage.initialize_empty_session(test_session)
    print(f"[OK] Created test session: {test_session}")
    
    # Verify both exist in storage
    assert storage.session_exists(user_session)
    assert storage.session_exists(test_session)
    print(f"[OK] Both sessions exist in storage")
    
    # List sessions should only show user session
    listed_sessions = storage.list_sessions()
    session_ids = [s["session_id"] for s in listed_sessions]
    
    assert user_session in session_ids, "User session should be in list"
    assert test_session not in session_ids, "Test session should be filtered out"
    print(f"[OK] Test session filtered out from list")
    print(f"[OK] Only user sessions shown: {len(listed_sessions)} sessions")
    
    ctx.cleanup()
    print("[PASS] Test passed: session filtering")


def test_mode_isolation():
    """Test that basic and deep modes have isolated storage."""
    print("\n=== Test: mode isolation (basic vs deep) ===")
    
    # Create basic mode context
    ctx_basic = MockContext("basic", "mode_isolation_basic")
    basic_session = ctx_basic.session_manager.create_new_session()
    ctx_basic.global_memory.storage.save_session(basic_session, [
        HumanMessage(content="Basic mode message")
    ])
    print(f"[OK] Created basic mode session: {basic_session[:20]}...")
    
    # Create deep mode context
    ctx_deep = MockContext("deep", "mode_isolation_deep")
    deep_session = ctx_deep.session_manager.create_new_session()
    ctx_deep.global_memory.storage.save_session(deep_session, [
        HumanMessage(content="Deep mode message")
    ])
    print(f"[OK] Created deep mode session: {deep_session[:20]}...")
    
    # Verify isolation
    basic_sessions = ctx_basic.global_memory.list_sessions()
    deep_sessions = ctx_deep.global_memory.list_sessions()
    
    basic_ids = [s["session_id"] for s in basic_sessions]
    deep_ids = [s["session_id"] for s in deep_sessions]
    
    assert basic_session in basic_ids, "Basic session should be in basic list"
    assert basic_session not in deep_ids, "Basic session should not be in deep list"
    assert deep_session in deep_ids, "Deep session should be in deep list"
    assert deep_session not in basic_ids, "Deep session should not be in basic list"
    
    print(f"[OK] Basic mode has {len(basic_sessions)} sessions")
    print(f"[OK] Deep mode has {len(deep_sessions)} sessions")
    print(f"[OK] Verified storage isolation between modes")
    
    ctx_basic.cleanup()
    ctx_deep.cleanup()
    print("[PASS] Test passed: mode isolation")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Session Management Commands Test Suite")
    print("="*60)
    
    tests = [
        test_new_session_command,
        test_list_sessions_command,
        test_clear_session_command,
        test_restore_session_command,
        test_delete_session_command,
        test_cleanup_orphaned_sessions,
        test_cleanup_old_sessions,
        test_session_filtering,
        test_mode_isolation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] Test failed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test error: {test.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

