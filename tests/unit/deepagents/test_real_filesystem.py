"""Unit tests for the real filesystem middleware."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.components.deepagents.runtime_middlewares.real_filesystem.middleware import (
    RealFilesystemMiddleware,
)


class TestRealFilesystemMiddleware(unittest.TestCase):
    """Validate core behaviours of the real filesystem middleware tools."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

        # Create directories and files
        (self.project_root / "src").mkdir()
        (self.project_root / "docs").mkdir()

        (self.project_root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (self.project_root / "src" / "notes.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
        (self.project_root / "docs" / ".secret.txt").write_text("hidden\n", encoding="utf-8")
        (self.project_root / "README.md").write_text("readme\n", encoding="utf-8")

        # Build middleware with tight security bounds to exercise behaviour
        self.config = {
            "enabled": True,
            "project_root": str(self.project_root),
            "security": {
                "allowed_paths": ["${PROJECT_ROOT}"],
                "allowed_extensions": [".py", ".txt", ".md"],
                "max_file_size": 40,  # bytes
            },
            "advanced": {
                "ignore_hidden_files": True,
            },
            "performance": {
                "list_max_results": 10,
                "glob_max_results": 10,
                "grep_max_results": 5,
                "grep_max_file_size": 1024,
            },
        }
        self.middleware = RealFilesystemMiddleware(config=self.config)
        tools = {tool.name: tool for tool in self.middleware.get_tools()}
        self.list_tool = tools["list_real_files"]
        self.read_tool = tools["read_real_file"]
        self.glob_tool = tools["glob_real_files"]
        self.grep_tool = tools["grep_real_files"]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_list_real_files_default_scope(self) -> None:
        """Listing without parameters should include visible project files."""
        result = self.list_tool.invoke(
            {
                "directory_path": None,
                "recursive": False,
                "include_hidden": False,
            }
        )
        self.assertIn("README.md", result)
        self.assertNotIn(".secret.txt", result, "hidden files should be omitted by default")

    def test_list_real_files_recursive(self) -> None:
        """Recursive listing should capture nested files once allowed."""
        result = self.list_tool.invoke(
            {
                "directory_path": str(self.project_root),
                "recursive": True,
                "include_hidden": False,
            }
        )
        expected = {
            "README.md",
            "src/main.py",
            "src/notes.txt",
        }
        self.assertTrue(expected.issubset(set(result)))

    def test_read_real_file_paginates_and_formats(self) -> None:
        """Reading a file should return formatted content with header."""
        output = self.read_tool.invoke(
            {
                "file_path": str(self.project_root / "src" / "notes.txt"),
                "offset": 1,
                "limit": 2,
                "encoding": "utf-8",
            }
        )
        self.assertIn("# src/notes.txt", output)
        self.assertIn("     2\tline2", output)
        self.assertIn("     3\tline3", output)

    def test_read_real_file_respects_size_limit(self) -> None:
        """Files exceeding the configured limit should be rejected."""
        (self.project_root / "big.txt").write_text("x" * 50, encoding="utf-8")
        message = self.read_tool.invoke(
            {
                "file_path": str(self.project_root / "big.txt"),
                "offset": 0,
                "limit": 10,
            }
        )
        self.assertIn("exceeds the limit", message)

    def test_list_real_files_respects_allowed_extensions(self) -> None:
        """Disallowed extensions are filtered out."""
        (self.project_root / "src" / "binary.bin").write_bytes(b"\x00")
        result = self.list_tool.invoke(
            {
                "directory_path": str(self.project_root / "src"),
                "recursive": False,
                "include_hidden": False,
            }
        )
        self.assertNotIn("src/binary.bin", result)

    def test_glob_real_files_matches_pattern(self) -> None:
        """Glob tool should match files according to pattern."""
        results = self.glob_tool.invoke(
            {
                "pattern": "*.py",
                "base_path": str(self.project_root / "src"),
                "recursive": False,
                "include_hidden": False,
            }
        )
        self.assertIn("src/main.py", results)
        self.assertNotIn("docs/.secret.txt", results)

    def test_grep_real_files_finds_pattern(self) -> None:
        """Grep should return matches with context."""
        output = self.grep_tool.invoke(
            {
                "pattern": r"line2",
                "file_pattern": "**/*.txt",
                "base_path": str(self.project_root),
                "case_sensitive": True,
                "context_lines": 1,
                "max_results": 3,
                "include_hidden": False,
            }
        )
        self.assertIn("# src/notes.txt:2", output)
        self.assertIn("     1\tline1", output)
        self.assertIn("     2\tline2", output)

    def test_grep_real_files_handles_no_matches(self) -> None:
        """Grep should return friendly message when nothing matches."""
        output = self.grep_tool.invoke(
            {
                "pattern": "does-not-exist",
                "file_pattern": "**/*.py",
                "base_path": str(self.project_root),
            }
        )
        self.assertEqual(output, "No matches found.")


if __name__ == "__main__":
    unittest.main()
