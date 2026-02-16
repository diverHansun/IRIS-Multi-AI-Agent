"""Integration tests for shell HITL workflow."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from langgraph.types import Interrupt

from src.application.services.agent.deep.hitl.handler import (
    handle_hitl_interrupt,
    HITLDecisionError,
    _resolve_decision,
)
from src.application.services.agent.deep.hitl.session_manager import SessionHITLManager


class TestExecuteShellHITLIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for shell HITL approval flow."""

    async def test_execute_shell_interrupt_handling(self):
        """Test that shell interrupt is properly handled."""
        # Create mock context
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()
        ctx.console.input = MagicMock(return_value="1")  # User approves

        # Create HITL manager
        hitl_manager = SessionHITLManager()

        # Create interrupt with shell action
        interrupt_value = {
            "action_requests": [
                {
                    "name": "shell",
                    "args": {
                        "command": "ls -la",
                        "timeout": 30,
                    },
                    "description": "Execute shell command",
                }
            ],
            "review_configs": [
                {
                    "action_name": "shell",
                    "allowed_decisions": ["approve", "reject"],
                }
            ],
        }

        interrupt = MagicMock(spec=Interrupt)
        interrupt.value = interrupt_value

        # Handle the interrupt
        responses = await handle_hitl_interrupt(
            ctx,
            [interrupt],
            hitl_manager,
            hitl_config=None,
        )

        # Verify response structure
        self.assertEqual(len(responses), 1)
        self.assertIn("decisions", responses[0])
        self.assertEqual(len(responses[0]["decisions"]), 1)
        self.assertEqual(responses[0]["decisions"][0]["type"], "approve")

        # Verify preview was displayed (console.print was called)
        self.assertTrue(ctx.console.print.called)
        print_calls = [str(call) for call in ctx.console.print.call_args_list]
        print_output = "\n".join(print_calls)

        # Check for key elements in the output
        self.assertTrue(any("shell" in str(call).lower() for call in print_calls))

    async def test_execute_shell_preview_display(self):
        """Test that shell preview is correctly formatted and displayed."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()
        ctx.console.input = MagicMock(return_value="1")

        hitl_manager = SessionHITLManager()

        request = {
            "name": "shell",
            "args": {
                "command": "touch test_file.txt",
                "timeout": 60,
                "env": {
                    "PATH": "/custom/path",
                }
            },
            "description": "Create test file",
        }

        config = {
            "action_name": "shell",
            "allowed_decisions": ["approve", "reject"],
        }

        # Call _resolve_decision directly to test preview
        decision = await _resolve_decision(ctx, request, config, hitl_manager)

        # Verify decision
        self.assertEqual(decision["type"], "approve")

        # Verify preview information was displayed
        print_calls = [str(call) for call in ctx.console.print.call_args_list]
        print_output = "\n".join(print_calls)

        # Check for preview details
        self.assertTrue(any("Execute Shell Command" in str(call) for call in print_calls))
        self.assertTrue(any("touch test_file.txt" in str(call) for call in print_calls))
        self.assertTrue(any("Timeout: 60 seconds" in str(call) for call in print_calls))
        self.assertTrue(any("Environment overrides" in str(call) for call in print_calls))

    async def test_execute_shell_rejection(self):
        """Test that shell can be rejected."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()
        ctx.console.input = MagicMock(side_effect=["3", "Security concern"])  # Reject with message

        hitl_manager = SessionHITLManager()

        request = {
            "name": "shell",
            "args": {
                "command": "rm -rf /",
            },
            "description": "Dangerous command",
        }

        config = {
            "action_name": "shell",
            "allowed_decisions": ["approve", "reject"],
        }

        decision = await _resolve_decision(ctx, request, config, hitl_manager)

        # Verify rejection
        self.assertEqual(decision["type"], "reject")
        self.assertIn("message", decision)
        self.assertEqual(decision["message"], "Security concern")

    async def test_execute_shell_with_missing_command(self):
        """Test handling of shell with missing command."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()
        ctx.console.input = MagicMock(return_value="1")

        hitl_manager = SessionHITLManager()

        request = {
            "name": "shell",
            "args": {},  # Missing command
            "description": "Shell execution",
        }

        config = {
            "action_name": "shell",
            "allowed_decisions": ["approve", "reject"],
        }

        # Should still work, but preview will be None
        decision = await _resolve_decision(ctx, request, config, hitl_manager)

        self.assertEqual(decision["type"], "approve")

    async def test_execute_shell_auto_approval(self):
        """Test auto-approval for shell."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()

        hitl_manager = SessionHITLManager()
        hitl_manager.register_auto_approval("shell")

        request = {
            "name": "shell",
            "args": {
                "command": "echo hello",
            },
            "description": "Simple echo",
        }

        config = {
            "action_name": "shell",
            "allowed_decisions": ["approve", "reject"],
        }

        decision = await _resolve_decision(ctx, request, config, hitl_manager)

        # Should auto-approve without prompting
        self.assertEqual(decision["type"], "approve")

        # Verify auto-approval message was printed
        print_calls = [str(call) for call in ctx.console.print.call_args_list]
        self.assertTrue(any("Auto-approved" in str(call) for call in print_calls))


class TestHITLExceptionHandling(unittest.IsolatedAsyncioTestCase):
    """Test exception handling in HITL flow."""

    async def test_missing_interrupt_payload_raises_error(self):
        """Test that missing interrupt payload raises HITLDecisionError."""
        ctx = MagicMock()
        ctx.console = MagicMock()

        hitl_manager = SessionHITLManager()

        # Create interrupt with None value
        interrupt = MagicMock(spec=Interrupt)
        interrupt.value = None

        with self.assertRaises(HITLDecisionError) as cm:
            await handle_hitl_interrupt(ctx, [interrupt], hitl_manager, None)

        self.assertIn("missing required fields", str(cm.exception))

    async def test_missing_action_requests_raises_error(self):
        """Test that missing action_requests raises HITLDecisionError."""
        ctx = MagicMock()
        ctx.console = MagicMock()

        hitl_manager = SessionHITLManager()

        interrupt_value = {
            "review_configs": [],
        }

        interrupt = MagicMock(spec=Interrupt)
        interrupt.value = interrupt_value

        with self.assertRaises(HITLDecisionError) as cm:
            await handle_hitl_interrupt(ctx, [interrupt], hitl_manager, None)

        self.assertIn("does not include action requests", str(cm.exception))


class TestMultipleToolsIntegration(unittest.IsolatedAsyncioTestCase):
    """Test HITL with multiple different tool types."""

    async def test_mixed_tools_approval(self):
        """Test handling interrupts with shell and file operations."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.console.print = MagicMock()
        # First approve shell, then approve write_real_file
        ctx.console.input = MagicMock(side_effect=["1", "1"])

        hitl_manager = SessionHITLManager()

        interrupt_value = {
            "action_requests": [
                {
                    "name": "shell",
                    "args": {"command": "mkdir test_dir"},
                    "description": "Create directory",
                },
                {
                    "name": "write_real_file",
                    "args": {
                        "file_path": "test_dir/test.txt",
                        "content": "Test content",
                        "encoding": "utf-8",
                    },
                    "description": "Write test file",
                },
            ],
            "review_configs": [
                {"action_name": "shell", "allowed_decisions": ["approve", "reject"]},
                {"action_name": "write_real_file", "allowed_decisions": ["approve", "reject"]},
            ],
        }

        interrupt = MagicMock(spec=Interrupt)
        interrupt.value = interrupt_value

        responses = await handle_hitl_interrupt(ctx, [interrupt], hitl_manager, None)

        # Verify both decisions
        self.assertEqual(len(responses), 1)
        decisions = responses[0]["decisions"]
        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0]["type"], "approve")
        self.assertEqual(decisions[1]["type"], "approve")


if __name__ == "__main__":
    unittest.main()
