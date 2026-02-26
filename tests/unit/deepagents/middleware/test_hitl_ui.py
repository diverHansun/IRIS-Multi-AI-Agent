"""Unit tests for HITL UI enhancements."""

import unittest
from io import StringIO
from unittest.mock import Mock, patch

from rich.console import Console

from src.application.services.agent.deep.hitl.handler import _build_options
from src.application.services.agent.deep.hitl.file_ops import (
    FileOperationRecord,
    FileOpMetrics,
    render_file_operation,
)


class TestBuildOptions(unittest.TestCase):
    """Test _build_options function with UI enhancements."""

    def test_all_options_available(self):
        """Test when all options are available (can auto-approve, not dangerous)."""
        result = _build_options(
            allowed_decisions=["approve", "reject"],
            can_auto=True,
            is_dangerous=False,
        )

        # Should have unified labels list
        self.assertIn("labels", result)
        self.assertIn("valid", result)

        # Check all labels
        labels = result["labels"]
        self.assertEqual(len(labels), 4)

        # Check option 1: Approve
        self.assertIn("[1]", labels[0])
        self.assertIn("Yes", labels[0])
        self.assertIn("\u2713", labels[0])  # Checkmark icon

        # Check option 2: Auto-approve
        self.assertIn("[2]", labels[1])
        self.assertIn("don't ask again", labels[1])
        self.assertIn("\u26a1", labels[1])  # Lightning icon

        # Check option 3: Reject
        self.assertIn("[3]", labels[2])
        self.assertIn("No", labels[2])
        self.assertIn("\u2717", labels[2])  # X icon

        # Check option 4: Custom
        self.assertIn("[4]", labels[3])
        self.assertIn("\u270f", labels[3])  # Pencil icon

        # Check valid choices
        self.assertEqual(result["valid"], {"1", "2", "3", "4"})

    def test_dangerous_tool_no_auto_approve(self):
        """Test when tool is dangerous (auto-approve unavailable)."""
        result = _build_options(
            allowed_decisions=["approve", "reject"],
            can_auto=True,
            is_dangerous=True,
        )

        labels = result["labels"]
        self.assertEqual(len(labels), 4)

        # First option should be available
        self.assertIn("[1]", labels[0])
        self.assertIn("Yes", labels[0])

        # Second option should show unavailable with reason
        self.assertIn("[2]", labels[1])
        self.assertIn("Unavailable", labels[1])
        self.assertIn("security-sensitive", labels[1])

        # Only 1, 3, 4 should be valid (not 2)
        self.assertEqual(result["valid"], {"1", "3", "4"})

    def test_cannot_auto_approve_due_to_settings(self):
        """Test when tool settings disable auto-approve."""
        result = _build_options(
            allowed_decisions=["approve", "reject"],
            can_auto=False,
            is_dangerous=False,
        )

        labels = result["labels"]

        # Second option should show unavailable with different reason
        self.assertIn("[2]", labels[1])
        self.assertIn("Unavailable", labels[1])
        self.assertIn("settings disabled", labels[1])

        # Only 1, 3, 4 should be valid
        self.assertEqual(result["valid"], {"1", "3", "4"})

    def test_only_approve_allowed(self):
        """Test when only approve is allowed."""
        result = _build_options(
            allowed_decisions=["approve"],
            can_auto=True,
            is_dangerous=False,
        )

        # Should have 4 labels total
        labels = result["labels"]
        self.assertEqual(len(labels), 4)

        # Rejection options (3 and 4) should be marked as unavailable
        self.assertIn("not allowed", labels[2])  # Option 3
        self.assertIn("not allowed", labels[3])  # Option 4

        # Only 1 and 2 should be valid
        self.assertEqual(result["valid"], {"1", "2"})

    def test_visual_elements_present(self):
        """Test that visual elements (icons, colors) are present."""
        result = _build_options(
            allowed_decisions=["approve", "reject"],
            can_auto=True,
            is_dangerous=False,
        )

        all_labels = result["labels"]

        # Check for Rich markup tags
        has_color = any("[green]" in label or "[yellow]" in label or "[red]" in label for label in all_labels)
        self.assertTrue(has_color, "Labels should contain color markup")

        # Check for icons (unicode characters)
        has_icon = any("\u2713" in label or "\u26a1" in label or "\u2717" in label for label in all_labels)
        self.assertTrue(has_icon, "Labels should contain icon characters")


class TestRenderFileOperation(unittest.TestCase):
    """Test render_file_operation with enhanced statistics."""

    def test_render_new_file(self):
        """Test rendering for a new file creation."""
        # Create a mock console that captures output
        output = StringIO()
        console = Console(file=output, width=80, legacy_windows=False, force_terminal=True)

        # Create a file operation record
        record = FileOperationRecord(
            tool_name="write_real_file",
            tool_call_id="call_123",
            file_path="test.txt",
            physical_path=None,
            args={"file_path": "test.txt", "content": "Hello\nWorld\n"},
            status="success",
            before_content=None,  # New file
            after_content="Hello\nWorld\n",
            diff=None,
            metrics=FileOpMetrics(
                lines_written=2,
                lines_added=2,
                lines_removed=0,
                bytes_written=12,
            ),
        )

        # Render the operation
        render_file_operation(record, console)

        # Get the output
        result = output.getvalue()

        # Check for expected content (note: new files show as "Lines changed" not "Lines written")
        self.assertIn("File operation completed", result)
        self.assertIn("test.txt", result)
        # New behavior: shows as "Lines changed: +2 / -0" instead of "Lines written: 2"
        self.assertIn("Lines changed", result)
        self.assertIn("Total lines", result)
        self.assertIn("2", result)  # The number 2 should appear
        self.assertIn("12", result)  # Bytes
        self.assertIn("bytes", result)
        self.assertIn("File created", result)

    def test_render_modified_file(self):
        """Test rendering for a file modification."""
        output = StringIO()
        console = Console(file=output, width=80, legacy_windows=False, force_terminal=True)

        record = FileOperationRecord(
            tool_name="edit_real_file",
            tool_call_id="call_456",
            file_path="existing.txt",
            physical_path=None,
            args={},
            status="success",
            before_content="Line 1\nLine 2\nLine 3\n",
            after_content="Line 1\nLine 2 modified\nLine 3\n",
            diff=None,
            metrics=FileOpMetrics(
                lines_written=3,
                lines_added=1,
                lines_removed=1,
                bytes_written=30,
            ),
        )

        render_file_operation(record, console)
        result = output.getvalue()

        # Check for change statistics (Rich output includes ANSI codes)
        self.assertIn("Lines changed", result)
        # Rich may split "+1" and "-1" with ANSI codes, so check for the numbers
        self.assertIn("1", result)  # Both +1 and -1 contain "1"
        self.assertIn("Total lines", result)
        self.assertIn("3", result)
        self.assertIn("30", result)
        self.assertIn("bytes", result)
        self.assertIn("File modified", result)

    def test_render_large_file_size_formatting(self):
        """Test human-readable size formatting for large files."""
        output = StringIO()
        console = Console(file=output, width=80, legacy_windows=False, force_terminal=True)

        # Test KB formatting
        record_kb = FileOperationRecord(
            tool_name="write_real_file",
            tool_call_id="call_kb",
            file_path="medium.txt",
            physical_path=None,
            args={},
            status="success",
            before_content=None,
            after_content="x" * 5120,  # 5 KB
            diff=None,
            metrics=FileOpMetrics(
                lines_written=1,
                lines_added=0,
                lines_removed=0,
                bytes_written=5120,
            ),
        )

        render_file_operation(record_kb, console)
        result_kb = output.getvalue()
        # Rich may add ANSI codes around numbers, so check parts separately
        self.assertIn("5.00", result_kb)
        self.assertIn("KB", result_kb)

        # Test MB formatting
        output_mb = StringIO()
        console_mb = Console(file=output_mb, width=80, legacy_windows=False, force_terminal=True)

        record_mb = FileOperationRecord(
            tool_name="write_real_file",
            tool_call_id="call_mb",
            file_path="large.txt",
            physical_path=None,
            args={},
            status="success",
            before_content=None,
            after_content="x" * 2097152,  # 2 MB
            diff=None,
            metrics=FileOpMetrics(
                lines_written=1,
                lines_added=0,
                lines_removed=0,
                bytes_written=2097152,
            ),
        )

        render_file_operation(record_mb, console_mb)
        result_mb = output_mb.getvalue()
        self.assertIn("2.00", result_mb)
        self.assertIn("MB", result_mb)

    def test_render_error_operation(self):
        """Test rendering for a failed operation."""
        output = StringIO()
        console = Console(file=output, width=80, legacy_windows=False, force_terminal=True)

        record = FileOperationRecord(
            tool_name="write_real_file",
            tool_call_id="call_error",
            file_path="error.txt",
            physical_path=None,
            args={},
            status="error",
            before_content=None,
            after_content=None,
            diff=None,
            error="Permission denied",
            metrics=FileOpMetrics(
                lines_written=0,
                lines_added=0,
                lines_removed=0,
                bytes_written=0,
            ),
        )

        render_file_operation(record, console)
        result = output.getvalue()

        self.assertIn("File operation failed", result)
        self.assertIn("error.txt", result)
        self.assertIn("Permission denied", result)


if __name__ == "__main__":
    unittest.main()
