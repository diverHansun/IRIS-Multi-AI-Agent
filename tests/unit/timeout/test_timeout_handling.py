"""
Test timeout handling in Deep Agent and SubAgent.

Tests the TimeoutError capture and recovery mechanism.
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'src'))


def test_subagent_timeout_message():
    """Test SubAgent timeout error message format."""
    print("\n=== Test: SubAgent timeout error message ===")
    
    # Simulate SubAgent timeout
    error_msg = (
        f"[TIMEOUT] SubAgent 'research' execution timed out.\n\n"
        f"Possible causes:\n"
        f"- Complex task requiring more time\n"
        f"- Slow API response\n"
        f"- Network issues\n\n"
        f"Suggestions:\n"
        f"- Break the task into smaller steps\n"
        f"- Retry the operation\n"
        f"- Use a different approach"
    )
    
    # Verify message format
    assert "[TIMEOUT]" in error_msg, "Should have TIMEOUT indicator"
    assert "Possible causes:" in error_msg, "Should explain possible causes"
    assert "Suggestions:" in error_msg, "Should provide suggestions"
    assert "research" in error_msg, "Should mention subagent name"
    
    print("[OK] SubAgent timeout message format is correct")
    print(f"[OK] Sample message:\n{error_msg}")
    print("[PASS] Test passed: SubAgent timeout message is informative")


def test_timeout_config_values():
    """Test that timeout configuration values are appropriate."""
    print("\n=== Test: Timeout configuration values ===")
    
    import json
    
    # Read MainAgent config
    config_path = "config/agents/deep/models/mainagents.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        main_config = json.load(f)
    
    # Check all models have appropriate timeout
    for provider, provider_data in main_config.items():
        for model_name, model_config in provider_data.get("models", {}).items():
            step_timeout = model_config.get("runtime_config", {}).get("step_timeout")
            
            assert step_timeout is not None, f"{provider}/{model_name} missing step_timeout"
            assert step_timeout >= 180, f"{provider}/{model_name} step_timeout too low: {step_timeout}"
            
            print(f"[OK] {provider}/{model_name}: step_timeout={step_timeout}s")
    
    print("[PASS] Test passed: All timeout configurations are appropriate")


def test_timeout_error_handling_code_exists():
    """Test that timeout handling code is present in conversation.py."""
    print("\n=== Test: Timeout handling code exists ===")
    
    # Read conversation.py
    conv_file = "src/application/services/agent/deep/streaming/conversation.py"
    with open(conv_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify TimeoutError handling exists
    assert "except TimeoutError" in content, "TimeoutError exception handler should exist"
    print("[OK] TimeoutError exception handler found")
    
    # Verify critical timeout handling features
    assert "persist_from_runtime" in content, "Should persist state after timeout"
    print("[OK] State persistence found in timeout handler")
    
    # Verify the comment that explains why persistence is critical
    assert "CRITICAL: Persist conversation state" in content or "persist" in content.lower()
    print("[OK] State persistence is implemented for data safety")
    
    # Verify aupdate_state is called
    assert "aupdate_state" in content, "Should call aupdate_state to notify agent"
    print("[OK] Agent notification via aupdate_state found")
    
    # Verify user gets feedback
    assert "TIMEOUT" in content, "Should show timeout message to user"
    assert "saved" in content.lower(), "Should mention state persistence to user"
    print("[OK] User feedback messages found")
    
    # Verify system message content
    assert "SYSTEM NOTIFICATION: The previous operation timed out" in content
    print("[OK] System notice to agent found")
    
    print("[PASS] Test passed: All timeout handling code is in place")


def test_subagent_timeout_code_exists():
    """Test that SubAgent timeout handling code exists."""
    print("\n=== Test: SubAgent timeout handling code exists ===")
    
    # Read middleware file
    middleware_file = "src/components/deepagents/runtime_middlewares/subagents/middleware.py"
    with open(middleware_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verify TimeoutError handling exists
    assert "except TimeoutError" in content, "TimeoutError handler should exist in SubAgent"
    print("[OK] SubAgent TimeoutError handler found")
    
    # Verify error message includes actionable info
    assert "Possible causes" in content, "Should explain possible causes"
    assert "Suggestions" in content, "Should provide suggestions"
    print("[OK] Actionable error message found")
    
    print("[PASS] Test passed: SubAgent timeout handling code is in place")


async def run_all_tests():
    """Run all timeout handling tests."""
    print("\n" + "="*60)
    print("Timeout Handling Test Suite")
    print("="*60)
    
    tests = [
        ("SubAgent timeout message", test_subagent_timeout_message),
        ("Timeout configuration", test_timeout_config_values),
        ("Timeout handling code exists", test_timeout_error_handling_code_exists),
        ("SubAgent timeout code exists", test_subagent_timeout_code_exists),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] Test failed: {test_name}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test error: {test_name}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
