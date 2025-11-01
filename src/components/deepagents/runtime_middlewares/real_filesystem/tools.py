"""Tool implementations for the real filesystem middleware."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from langchain_core.tools import BaseTool, tool

from .config import RealFilesystemOptions
from .security import (
    FileTooLargeError,
    PathValidationError,
    RealFilesystemError,
    ensure_directory_access,
    validate_directory,
    validate_file,
)
from .utils import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    EMPTY_CONTENT_WARNING,
    format_with_line_numbers,
    is_hidden_path,
    relative_display_path,
)

LIST_TOOL_NAME = "list_real_files"
READ_TOOL_NAME = "read_real_file"

LIST_PROMPT = """List files from the host machine within the configured allowlist.

Usage guidelines:
- Provide an optional path relative to the project root (defaults to project root).
- Set recursive=true to include files in subdirectories.
- Hidden files are omitted unless include_hidden=true."""

READ_PROMPT = """Read contents from a file on the host machine with line numbers.

Usage guidelines:
- File paths can be absolute or relative to the project root.
- Only text files with allowed extensions can be accessed.
- Use offset and limit for pagination to avoid large outputs.
- Encoding defaults to UTF-8; specify another encoding if required."""


@dataclass(slots=True)
class RealFilesystemToolFactory:
    """Factory for constructing real filesystem tools."""

    options: RealFilesystemOptions

    def build_list_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or LIST_PROMPT

        @tool(LIST_TOOL_NAME, description=prompt)
        def list_real_files(
            directory_path: str | None = None,
            recursive: bool = False,
            include_hidden: bool = False,
        ) -> List[str] | str:
            try:
                directory = validate_directory(directory_path, self.options)
            except PathValidationError as exc:
                return str(exc)

            skip_hidden = self.options.advanced.ignore_hidden_files and not include_hidden
            max_items = max(1, self.options.performance.list_max_results)
            results: List[str] = []
            truncated = False
            iterator = directory.rglob("*") if recursive else directory.iterdir()
            try:
                for path in iterator:
                    if not path.is_file():
                        continue
                    try:
                        ensure_directory_access(path, self.options)
                    except PathValidationError:
                        continue
                    try:
                        relative_candidate = path.relative_to(self.options.project_root)
                    except ValueError:
                        relative_candidate = path
                    if skip_hidden and is_hidden_path(relative_candidate):
                        continue
                    extensions = self.options.security.allowed_extensions
                    if "*" not in extensions:
                        suffix = path.suffix.lower()
                        if suffix:
                            if suffix not in extensions:
                                continue
                        else:
                            if "" not in extensions:
                                continue
                    results.append(relative_display_path(path, self.options.project_root))
                    if len(results) >= max_items:
                        truncated = True
                        break
            except OSError as exc:
                return f"Failed to list '{directory}': {exc}"

            if truncated:
                results.append(f"... truncated at {max_items} results")

            return results

        return list_real_files

    def build_read_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or READ_PROMPT

        @tool(READ_TOOL_NAME, description=prompt)
        def read_real_file(
            file_path: str,
            offset: int = DEFAULT_READ_OFFSET,
            limit: int = DEFAULT_READ_LIMIT,
            encoding: str = "utf-8",
        ) -> str:
            if offset < 0:
                return "Offset must be greater than or equal to 0"
            if limit <= 0:
                return "Limit must be greater than 0"

            try:
                path = validate_file(file_path, self.options)
            except FileTooLargeError as exc:
                return str(exc)
            except FileNotFoundError as exc:
                return str(exc)
            except (PathValidationError, RealFilesystemError) as exc:
                return str(exc)

            try:
                with path.open("r", encoding=encoding) as handle:
                    lines = handle.readlines()
            except UnicodeDecodeError:
                with path.open("r", encoding=encoding, errors="replace") as handle:
                    lines = handle.readlines()
            except LookupError:
                return f"Unsupported encoding '{encoding}'"
            except OSError as exc:
                return f"Failed to read '{path}': {exc}"

            if not lines:
                return EMPTY_CONTENT_WARNING
            if offset >= len(lines):
                return f"Offset {offset} exceeds file length ({len(lines)} lines)"

            end_index = min(offset + limit, len(lines))
            excerpt = [line.rstrip("\n") for line in lines[offset:end_index]]
            display_path = relative_display_path(path, self.options.project_root)

            formatted = format_with_line_numbers(excerpt, start_line=offset + 1)
            if end_index < len(lines):
                formatted += f"\n... truncated at line {end_index}"
            header = f"# {display_path}\n"
            return header + formatted

        return read_real_file

    def build_all(self) -> List[BaseTool]:
        return [self.build_list_tool(), self.build_read_tool()]
