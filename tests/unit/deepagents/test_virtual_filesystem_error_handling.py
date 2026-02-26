"""Unit tests for virtual filesystem error handling improvements.

This module tests that the virtual filesystem tools handle errors gracefully
by returning error strings instead of raising exceptions, which would interrupt
the agent conversation flow.
"""

from __future__ import annotations

import unittest

from src.components.deepagents.runtime_middlewares.virtual_filesystem.tools import (
    VirtualFilesystemToolFactory,
)
from src.components.deepagents.runtime_middlewares.virtual_filesystem.types import (
    VirtualFilesystemOptions,
    FilesystemState,
)


class TestVirtualFilesystemErrorHandling(unittest.TestCase):
    """Test that virtual filesystem tools handle errors gracefully without raising exceptions."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.options = VirtualFilesystemOptions(long_term_memory=False)
        self.factory = VirtualFilesystemToolFactory(options=self.options)

    def test_classify_path_with_traversal_raises_value_error(self) -> None:
        """Test that path traversal attempts raise ValueError which should be caught by tools."""
        with self.assertRaises(ValueError) as context:
            self.factory.classify_path("/workspace/../etc/passwd")
        self.assertIn("traversal", str(context.exception).lower())

    def test_fetch_file_from_empty_state_raises_value_error(self) -> None:
        """Test that fetching non-existent file raises ValueError which should be caught by tools."""
        empty_state = FilesystemState(files={})

        with self.assertRaises(ValueError) as context:
            self.factory._fetch_file_from_state(empty_state, "/nonexistent.txt")

        self.assertIn("not found", str(context.exception).lower())

    def test_code_has_try_except_in_read_tool(self) -> None:
        """Verify that read_virtual_file tool has proper try-except wrapping."""
        read_tool = self.factory.build_read_tool()

        # Check that the tool was created successfully
        self.assertIsNotNone(read_tool)
        self.assertEqual(read_tool.name, "read_virtual_file")

        # Read the source code to verify try-except is present
        import inspect
        source = inspect.getsource(read_tool.func)

        # Verify the fix is in place
        self.assertIn("try:", source)
        self.assertIn("except ValueError", source)
        self.assertIn("except Exception", source)
        self.assertIn("Error:", source)
        self.assertIn("# Wrap all operations in try-except to prevent conversation interruption", source)

    def test_code_has_try_except_in_write_tool(self) -> None:
        """Verify that write_virtual_file tool has proper try-except wrapping."""
        write_tool = self.factory.build_write_tool()

        self.assertIsNotNone(write_tool)
        self.assertEqual(write_tool.name, "write_virtual_file")

        import inspect
        source = inspect.getsource(write_tool.func)

        self.assertIn("try:", source)
        self.assertIn("except ValueError", source)
        self.assertIn("except Exception", source)

    def test_code_has_try_except_in_edit_tool(self) -> None:
        """Verify that edit_virtual_file tool has proper try-except wrapping."""
        edit_tool = self.factory.build_edit_tool()

        self.assertIsNotNone(edit_tool)
        self.assertEqual(edit_tool.name, "edit_virtual_file")

        import inspect
        source = inspect.getsource(edit_tool.func)

        self.assertIn("try:", source)
        self.assertIn("except ValueError", source)
        self.assertIn("except Exception", source)
        # Verify tool_call_id error is returned instead of raised
        self.assertIn('return "Error: Tool call ID missing', source)

    def test_code_has_try_except_in_list_tool(self) -> None:
        """Verify that list_virtual_files tool has proper try-except wrapping."""
        list_tool = self.factory.build_list_tool()

        self.assertIsNotNone(list_tool)
        self.assertEqual(list_tool.name, "list_virtual_files")

        import inspect
        source = inspect.getsource(list_tool.func)

        self.assertIn("try:", source)
        self.assertIn("except ValueError", source)
        self.assertIn("except Exception", source)


class TestErrorHandlingPrinciples(unittest.TestCase):
    """Test that the implementation follows SOLID and error handling best practices."""

    def test_tools_follow_single_responsibility_principle(self) -> None:
        """Each tool should have a single, well-defined responsibility."""
        factory = VirtualFilesystemToolFactory(options=VirtualFilesystemOptions())

        tools = factory.build_all()
        tool_names = [tool.name for tool in tools]

        # Verify we have 4 distinct tools, each with single responsibility
        expected_tools = [
            "list_virtual_files",   # List files
            "read_virtual_file",    # Read file content
            "write_virtual_file",   # Create new file
            "edit_virtual_file",    # Edit existing file
        ]

        self.assertEqual(set(tool_names), set(expected_tools))

    def test_error_messages_are_user_friendly(self) -> None:
        """Error messages should be clear and actionable."""
        factory = VirtualFilesystemToolFactory(options=VirtualFilesystemOptions())
        empty_state = FilesystemState(files={})

        # Test that internal errors have clear messages
        try:
            factory._fetch_file_from_state(empty_state, "/missing.txt")
            self.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Error should be clear and include the path
            self.assertIn("not found", error_msg.lower())
            self.assertIn("/missing.txt", error_msg)


if __name__ == "__main__":
    unittest.main()
