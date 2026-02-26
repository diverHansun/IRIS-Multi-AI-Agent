"""Unit tests for HITL preview builders."""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.application.services.agent.deep.hitl.preview import (
    build_approval_preview,
    _build_shell_preview,
    _build_write_preview,
    _build_edit_preview,
    ApprovalPreview,
)


class TestShellPreviewBuilder(unittest.TestCase):
    """Test shell command preview builder."""

    def test_build_shell_preview_basic_command(self):
        """Test basic shell command preview."""
        args = {
            "command": "ls -la",
        }

        preview = _build_shell_preview(args)

        self.assertIsNotNone(preview)
        self.assertIsInstance(preview, ApprovalPreview)
        self.assertEqual(preview.title, "Execute Shell Command")
        self.assertIn("Command: ls -la", preview.details)
        self.assertIn(f"Working directory: {Path.cwd()}", preview.details)
        self.assertIsNone(preview.diff)
        self.assertIsNone(preview.diff_title)
        self.assertIsNone(preview.error)

    def test_build_shell_preview_with_timeout(self):
        """Test shell command preview with timeout."""
        args = {
            "command": "sleep 100",
            "timeout": 30,
        }

        preview = _build_shell_preview(args)

        self.assertIsNotNone(preview)
        self.assertIn("Timeout: 30 seconds", preview.details)

    def test_build_shell_preview_with_env_overrides(self):
        """Test shell command preview with environment overrides."""
        args = {
            "command": "echo $PATH",
            "env": {
                "PATH": "/custom/path",
                "HOME": "/custom/home",
                "USER": "testuser",
            }
        }

        preview = _build_shell_preview(args)

        self.assertIsNotNone(preview)
        # Should show sorted environment variable keys
        env_detail = next((d for d in preview.details if "Environment overrides" in d), None)
        self.assertIsNotNone(env_detail)
        self.assertIn("HOME", env_detail)
        self.assertIn("PATH", env_detail)
        self.assertIn("USER", env_detail)

    def test_build_shell_preview_empty_command(self):
        """Test shell preview with empty command returns None."""
        args = {
            "command": "",
        }

        preview = _build_shell_preview(args)

        self.assertIsNone(preview)

    def test_build_shell_preview_no_command(self):
        """Test shell preview with missing command returns None."""
        args = {}

        preview = _build_shell_preview(args)

        self.assertIsNone(preview)

    def test_build_shell_preview_alternate_input_field(self):
        """Test shell preview using 'input' field instead of 'command'."""
        args = {
            "input": "touch test.txt",
        }

        preview = _build_shell_preview(args)

        self.assertIsNotNone(preview)
        self.assertIn("Command: touch test.txt", preview.details)


class TestBuildApprovalPreviewIntegration(unittest.TestCase):
    """Test main build_approval_preview function with different tool types."""

    def test_shell_tool(self):
        """Test that shell preview is properly routed."""
        args = {
            "command": "rm -rf /tmp/test",
        }

        preview = build_approval_preview("shell", args)

        self.assertIsNotNone(preview)
        self.assertEqual(preview.title, "Execute Shell Command")
        self.assertIn("Command: rm -rf /tmp/test", preview.details)

    def test_shell_tool_uses_supplied_workspace(self):
        """Shell preview should display the resolved shell workspace when provided."""
        args = {"command": "pwd"}

        preview = build_approval_preview("shell", args, shell_workspace=".")

        self.assertIsNotNone(preview)
        self.assertIn(f"Working directory: {Path.cwd().resolve()}", preview.details)

    def test_write_real_file_tool(self):
        """Test that write_real_file is properly routed."""
        args = {
            "file_path": "test.txt",
            "content": "Hello World",
            "encoding": "utf-8",
        }

        with patch("src.application.services.agent.deep.hitl.preview._resolve_path") as mock_resolve:
            with patch("src.application.services.agent.deep.hitl.preview._read_text") as mock_read:
                mock_path = MagicMock(spec=Path)
                mock_path.exists.return_value = False
                mock_resolve.return_value = mock_path
                mock_read.return_value = ""

                preview = build_approval_preview("write_real_file", args)

                self.assertIsNotNone(preview)
                self.assertIn("Write", preview.title)

    def test_edit_real_file_tool(self):
        """Test that edit_real_file is properly routed."""
        args = {
            "file_path": "test.txt",
            "old_string": "old",
            "new_string": "new",
            "encoding": "utf-8",
        }

        with patch("src.application.services.agent.deep.hitl.preview._resolve_path") as mock_resolve:
            with patch("src.application.services.agent.deep.hitl.preview._read_text") as mock_read:
                mock_path = MagicMock(spec=Path)
                mock_path.exists.return_value = True
                mock_resolve.return_value = mock_path
                mock_read.return_value = "This is old content"

                preview = build_approval_preview("edit_real_file", args)

                self.assertIsNotNone(preview)
                self.assertIn("Edit", preview.title)

    def test_unsupported_tool(self):
        """Test that unsupported tools return None."""
        args = {"some": "args"}

        preview = build_approval_preview("unsupported_tool", args)

        self.assertIsNone(preview)

    def test_none_args(self):
        """Test that None args returns None."""
        preview = build_approval_preview("shell", None)

        self.assertIsNone(preview)


class TestApprovalPreviewDataClass(unittest.TestCase):
    """Test ApprovalPreview dataclass structure."""

    def test_approval_preview_has_required_fields(self):
        """Test that ApprovalPreview has all required fields."""
        preview = ApprovalPreview(
            title="Test Title",
            details=["Detail 1", "Detail 2"],
            diff="some diff",
            diff_title="Diff Title",
            diff_truncated=False,
            warning="Some warning",
            error="Some error",
        )

        self.assertEqual(preview.title, "Test Title")
        self.assertEqual(preview.details, ["Detail 1", "Detail 2"])
        self.assertEqual(preview.diff, "some diff")
        self.assertEqual(preview.diff_title, "Diff Title")
        self.assertFalse(preview.diff_truncated)
        self.assertEqual(preview.warning, "Some warning")
        self.assertEqual(preview.error, "Some error")

    def test_approval_preview_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        preview = ApprovalPreview(
            title="Test",
            details=[],
        )

        self.assertIsNone(preview.diff)
        self.assertIsNone(preview.diff_title)
        self.assertFalse(preview.diff_truncated)
        self.assertIsNone(preview.warning)
        self.assertIsNone(preview.error)


class TestFileOpsPreviewBuilder(unittest.TestCase):
    """Test file operations preview builders."""

    def test_write_preview_includes_diff_title(self):
        """Test that write preview includes diff_title field."""
        args = {
            "file_path": "test.txt",
            "content": "New content",
            "encoding": "utf-8",
        }

        with patch("src.application.services.agent.deep.hitl.preview._resolve_path") as mock_resolve:
            with patch("src.application.services.agent.deep.hitl.preview._read_text") as mock_read:
                with patch("src.application.services.agent.deep.hitl.preview.compute_text_diff") as mock_diff:
                    mock_path = MagicMock(spec=Path)
                    mock_path.exists.return_value = False
                    mock_resolve.return_value = mock_path
                    mock_read.return_value = ""

                    # Mock DiffInfo object
                    diff_info = MagicMock()
                    diff_info.diff = "--- a/test.txt\n+++ b/test.txt\n@@ -0,0 +1,1 @@\n+New content"
                    diff_info.truncated = False
                    mock_diff.return_value = diff_info

                    preview = _build_write_preview(args)

                    self.assertIsNotNone(preview)
                    self.assertIsNotNone(preview.diff_title)
                    self.assertIn("Diff", preview.diff_title)

    def test_edit_preview_includes_diff_title(self):
        """Test that edit preview includes diff_title field."""
        args = {
            "file_path": "test.txt",
            "old_string": "old",
            "new_string": "new",
            "encoding": "utf-8",
        }

        with patch("src.application.services.agent.deep.hitl.preview._resolve_path") as mock_resolve:
            with patch("src.application.services.agent.deep.hitl.preview._read_text") as mock_read:
                with patch("src.application.services.agent.deep.hitl.preview.compute_text_diff") as mock_diff:
                    mock_path = MagicMock(spec=Path)
                    mock_path.exists.return_value = True
                    mock_resolve.return_value = mock_path
                    mock_read.return_value = "This is old text"

                    # Mock DiffInfo object
                    diff_info = MagicMock()
                    diff_info.diff = "--- a/test.txt\n+++ b/test.txt\n@@ -1,1 +1,1 @@\n-old\n+new"
                    diff_info.truncated = False
                    mock_diff.return_value = diff_info

                    preview = _build_edit_preview(args)

                    self.assertIsNotNone(preview)
                    self.assertIsNotNone(preview.diff_title)
                    self.assertIn("Diff", preview.diff_title)


if __name__ == "__main__":
    unittest.main()
