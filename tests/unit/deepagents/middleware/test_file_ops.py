"""Unit tests for file operation tracking and diff preview."""

import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

from src.application.services.agent.deep.hitl.file_ops import (
    FileOpTracker,
    build_approval_preview,
    compute_unified_diff,
    format_display_path,
    resolve_physical_path,
)


class TestDiffCalculation(unittest.TestCase):
    """Test diff calculation functions."""

    def test_compute_unified_diff_basic(self):
        """Test basic diff calculation."""
        before = "line 1\nline 2\nline 3"
        after = "line 1\nline 2 modified\nline 3"

        diff = compute_unified_diff(before, after, "test.txt")

        self.assertIsNotNone(diff)
        self.assertIn("test.txt (before)", diff)
        self.assertIn("test.txt (after)", diff)
        self.assertIn("-line 2", diff)
        self.assertIn("+line 2 modified", diff)

    def test_compute_unified_diff_no_change(self):
        """Test diff with no changes."""
        content = "line 1\nline 2\nline 3"

        diff = compute_unified_diff(content, content, "test.txt")

        self.assertIsNone(diff)

    def test_compute_unified_diff_truncation(self):
        """Test diff truncation for large files."""
        before = "\n".join([f"line {i}" for i in range(1000)])
        after = "\n".join([f"line {i} modified" for i in range(1000)])

        diff = compute_unified_diff(before, after, "test.txt", max_lines=50)

        self.assertIsNotNone(diff)
        lines = diff.splitlines()
        self.assertEqual(len(lines), 50)
        self.assertIn("(diff truncated)", lines[-1])


class TestPathHandling(unittest.TestCase):
    """Test path resolution and formatting."""

    def test_resolve_physical_path_absolute(self):
        """Test resolving absolute path."""
        path_str = str(Path.cwd() / "test.txt")
        result = resolve_physical_path(path_str)

        self.assertIsNotNone(result)
        self.assertTrue(result.is_absolute())

    def test_resolve_physical_path_relative(self):
        """Test resolving relative path."""
        result = resolve_physical_path("test.txt")

        self.assertIsNotNone(result)
        self.assertTrue(result.is_absolute())
        self.assertEqual(result.name, "test.txt")

    def test_resolve_physical_path_none(self):
        """Test handling None input."""
        result = resolve_physical_path(None)
        self.assertIsNone(result)

    def test_format_display_path(self):
        """Test path formatting for display."""
        # Absolute path shows filename only
        result = format_display_path(str(Path("/long/path/to/file.txt").absolute()))
        self.assertEqual(result, "file.txt")

        # Relative path shows as-is (use platform separator)
        rel_path = str(Path("relative") / "path.txt")
        result = format_display_path(rel_path)
        self.assertEqual(result, rel_path)

        # None returns unknown
        result = format_display_path(None)
        self.assertEqual(result, "(unknown)")


class TestApprovalPreview(unittest.TestCase):
    """Test approval preview generation."""

    def test_build_preview_write_new_file(self):
        """Test preview for writing new file."""
        args = {
            "file_path": "test.txt",
            "content": "Hello\nWorld",
        }

        preview = build_approval_preview("write_real_file", args)

        self.assertIsNotNone(preview)
        self.assertIn("Write", preview.title)
        self.assertTrue(any("Create new file" in d for d in preview.details))
        self.assertIsNotNone(preview.diff)
        self.assertIn("+Hello", preview.diff)
        self.assertIn("+World", preview.diff)

    def test_build_preview_write_existing_file(self):
        """Test preview for overwriting existing file."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Original content")
            temp_path = f.name

        try:
            args = {
                "file_path": temp_path,
                "content": "New content",
            }

            preview = build_approval_preview("write_real_file", args)

            self.assertIsNotNone(preview)
            self.assertTrue(any("overwrites existing" in d for d in preview.details))
            self.assertIsNotNone(preview.diff)
            self.assertIn("-Original content", preview.diff)
            self.assertIn("+New content", preview.diff)
        finally:
            Path(temp_path).unlink()

    def test_build_preview_edit_file(self):
        """Test preview for editing existing file."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Hello World\nGoodbye World")
            temp_path = f.name

        try:
            args = {
                "file_path": temp_path,
                "old_string": "World",
                "new_string": "Universe",
                "replace_all": False,
            }

            preview = build_approval_preview("edit_real_file", args)

            self.assertIsNotNone(preview)
            self.assertIn("Update", preview.title)
            self.assertTrue(any("single occurrence" in d for d in preview.details))
            self.assertIsNotNone(preview.diff)
            self.assertIn("-Hello World", preview.diff)
            self.assertIn("+Hello Universe", preview.diff)
        finally:
            Path(temp_path).unlink()

    def test_build_preview_edit_replace_all(self):
        """Test preview for edit with replace_all."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("World World World")
            temp_path = f.name

        try:
            args = {
                "file_path": temp_path,
                "old_string": "World",
                "new_string": "Earth",
                "replace_all": True,
            }

            preview = build_approval_preview("edit_real_file", args)

            self.assertIsNotNone(preview)
            self.assertTrue(any("all occurrences" in d for d in preview.details))
            self.assertTrue(any("Occurrences matched: 3" in d for d in preview.details))
        finally:
            Path(temp_path).unlink()

    def test_build_preview_edit_not_found(self):
        """Test preview when old_string not found."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Hello World")
            temp_path = f.name

        try:
            args = {
                "file_path": temp_path,
                "old_string": "NotFound",
                "new_string": "Something",
                "replace_all": False,
            }

            preview = build_approval_preview("edit_real_file", args)

            self.assertIsNotNone(preview)
            self.assertIsNotNone(preview.error)
            self.assertIn("not found", preview.error)
        finally:
            Path(temp_path).unlink()

    def test_build_preview_non_file_tool(self):
        """Test preview for non-file tools returns None."""
        args = {"query": "test"}
        preview = build_approval_preview("web_search", args)
        self.assertIsNone(preview)


class TestFileOpTracker(unittest.TestCase):
    """Test FileOpTracker functionality."""

    def test_start_operation_write(self):
        """Test starting write operation."""
        tracker = FileOpTracker()
        args = {"file_path": "test.txt", "content": "data"}

        tracker.start_operation("write_real_file", args, "call-123")

        self.assertIn("call-123", tracker.active)
        record = tracker.active["call-123"]
        self.assertEqual(record.tool_name, "write_real_file")
        self.assertEqual(record.status, "pending")

    def test_start_operation_ignores_non_file_tools(self):
        """Test that non-file tools are not tracked."""
        tracker = FileOpTracker()
        args = {"query": "test"}

        tracker.start_operation("web_search", args, "call-456")

        self.assertEqual(len(tracker.active), 0)

    def test_complete_with_message_success(self):
        """Test completing operation successfully."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Original")
            temp_path = f.name

        try:
            tracker = FileOpTracker()
            args = {"file_path": temp_path, "content": "Modified"}
            tracker.start_operation("write_real_file", args, "call-789")

            # Write the file
            Path(temp_path).write_text("Modified")

            # Create mock tool message
            tool_msg = Mock()
            tool_msg.tool_call_id = "call-789"
            tool_msg.content = "File written successfully"
            tool_msg.status = "success"

            record = tracker.complete_with_message(tool_msg)

            self.assertIsNotNone(record)
            self.assertEqual(record.status, "success")
            self.assertEqual(record.before_content, "Original")
            self.assertEqual(record.after_content, "Modified")
            self.assertIsNotNone(record.diff)
            self.assertIn("call-789", [r.tool_call_id for r in tracker.completed])
        finally:
            Path(temp_path).unlink()

    def test_complete_with_message_error(self):
        """Test completing operation with error."""
        tracker = FileOpTracker()
        args = {"file_path": "test.txt"}
        tracker.start_operation("write_real_file", args, "call-error")

        tool_msg = Mock()
        tool_msg.tool_call_id = "call-error"
        tool_msg.content = "Error: Permission denied"
        tool_msg.status = "error"

        record = tracker.complete_with_message(tool_msg)

        self.assertIsNotNone(record)
        self.assertEqual(record.status, "error")
        self.assertIn("Permission denied", record.error)

    def test_complete_bash_operation(self):
        """Test bash operations are recorded without diff."""
        tracker = FileOpTracker()
        args = {"command": "ls -la"}
        tracker.start_operation("bash", args, "call-bash")

        tool_msg = Mock()
        tool_msg.tool_call_id = "call-bash"
        tool_msg.content = "file1.txt\nfile2.txt"
        tool_msg.status = "success"

        record = tracker.complete_with_message(tool_msg)

        self.assertIsNotNone(record)
        self.assertEqual(record.status, "success")
        self.assertIsNone(record.diff)


if __name__ == "__main__":
    unittest.main()
