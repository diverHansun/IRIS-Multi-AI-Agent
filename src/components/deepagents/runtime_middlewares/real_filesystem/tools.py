"""Tool implementations for the real filesystem middleware."""

from __future__ import annotations

import re
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
    ensure_file_access,
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
GLOB_TOOL_NAME = "glob_real_files"
GREP_TOOL_NAME = "grep_real_files"

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

GLOB_PROMPT = """Search for files on the host machine using glob patterns.

Usage guidelines:
- Patterns follow Python's glob syntax (supports **, *, ?, and character sets).
- Provide base_path to scope the search (defaults to project root).
- Hidden files are skipped unless include_hidden=true.
- Results are limited to the configured maximum to prevent huge outputs."""

GREP_PROMPT = """Search file contents on the host machine using regular expressions.

Usage guidelines:
- pattern must be a valid Python regular expression.
- Optionally filter files with file_pattern (glob syntax) and base_path.
- Case sensitivity can be controlled with case_sensitive flag.
- context_lines adds lines before/after each match for additional context.
- Large files beyond configured limits are skipped automatically."""


@dataclass(slots=True)
class RealFilesystemToolFactory:
    """Factory for constructing real filesystem tools."""

    options: RealFilesystemOptions

    # ------------------------------------------------------------------ helper utilities
    def _is_allowed_file(self, path: Path, *, include_hidden: bool) -> bool:
        """Return whether a file should be exposed based on hidden rules and extensions."""
        try:
            relative_candidate = path.relative_to(self.options.project_root)
        except ValueError:
            relative_candidate = path

        if self.options.advanced.ignore_hidden_files and not include_hidden:
            if is_hidden_path(relative_candidate):
                return False

        extensions = self.options.security.allowed_extensions
        if "*" in extensions:
            return True
        suffix = path.suffix.lower()
        if suffix:
            return suffix in extensions
        return "" in extensions

    # ------------------------------------------------------------------ list tool
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
                    if not self._is_allowed_file(path, include_hidden=include_hidden):
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

    # ------------------------------------------------------------------ read tool
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

    # ------------------------------------------------------------------ glob tool
    def build_glob_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or GLOB_PROMPT

        @tool(GLOB_TOOL_NAME, description=prompt)
        def glob_real_files(
            pattern: str,
            base_path: str | None = None,
            recursive: bool = True,
            include_hidden: bool = False,
        ) -> List[str] | str:
            if not pattern:
                return "Pattern must not be empty"

            try:
                base_dir = validate_directory(base_path, self.options)
            except PathValidationError as exc:
                return str(exc)

            iterator = base_dir.rglob(pattern) if recursive else base_dir.glob(pattern)
            max_items = max(1, self.options.performance.glob_max_results)

            results: List[str] = []
            truncated = False
            try:
                for path in iterator:
                    if not path.is_file():
                        continue
                    try:
                        ensure_directory_access(path, self.options)
                    except PathValidationError:
                        continue
                    if not self._is_allowed_file(path, include_hidden=include_hidden):
                        continue
                    results.append(relative_display_path(path, self.options.project_root))
                    if len(results) >= max_items:
                        truncated = True
                        break
            except OSError as exc:
                return f"Failed to search '{base_dir}': {exc}"

            if truncated:
                results.append(f"... truncated at {max_items} results")

            return results

        return glob_real_files

    # ------------------------------------------------------------------ grep tool
    def build_grep_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or GREP_PROMPT

        @tool(GREP_TOOL_NAME, description=prompt)
        def grep_real_files(
            pattern: str,
            file_pattern: str | None = None,
            base_path: str | None = None,
            case_sensitive: bool = True,
            context_lines: int = 0,
            max_results: int | None = None,
            include_hidden: bool = False,
        ) -> str:
            if not pattern:
                return "Pattern must not be empty"
            if context_lines < 0:
                return "context_lines must be greater than or equal to 0"

            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)
            except re.error as exc:
                return f"Invalid regular expression: {exc}"

            try:
                base_dir = validate_directory(base_path, self.options)
            except PathValidationError as exc:
                return str(exc)

            search_glob = file_pattern or "**/*"
            iterator = base_dir.rglob(search_glob)

            configured_limit = max(1, self.options.performance.grep_max_results)
            requested_limit = max_results if max_results is not None else configured_limit
            limit = max(1, min(requested_limit, configured_limit))
            size_threshold = max(0, self.options.performance.grep_max_file_size)

            matches: List[str] = []
            exhausted = False
            try:
                for candidate in iterator:
                    if exhausted:
                        break
                    if not candidate.is_file():
                        continue
                    try:
                        ensure_file_access(candidate, self.options)
                    except FileTooLargeError:
                        # File exceeds general size limit; skip.
                        continue
                    except (PathValidationError, RealFilesystemError):
                        continue
                    if not self._is_allowed_file(candidate, include_hidden=include_hidden):
                        continue
                    try:
                        size = candidate.stat().st_size
                    except OSError:
                        continue
                    if size_threshold and size > size_threshold:
                        continue

                    try:
                        with candidate.open("r", encoding="utf-8") as handle:
                            lines = handle.readlines()
                    except UnicodeDecodeError:
                        with candidate.open("r", encoding="utf-8", errors="replace") as handle:
                            lines = handle.readlines()
                    except OSError:
                        continue

                    for idx, raw_line in enumerate(lines):
                        if not regex.search(raw_line):
                            continue
                        start = max(0, idx - context_lines)
                        end = min(len(lines), idx + context_lines + 1)
                        snippet = [line.rstrip("\n") for line in lines[start:end]]
                        formatted = format_with_line_numbers(snippet, start_line=start + 1)
                        header = f"# {relative_display_path(candidate, self.options.project_root)}:{idx + 1}"
                        matches.append(f"{header}\n{formatted}")
                        if len(matches) >= limit:
                            exhausted = True
                            break
            except OSError as exc:
                return f"Failed to search '{base_dir}': {exc}"

            if not matches:
                return "No matches found."
            return "\n\n".join(matches)

        return grep_real_files

    # ------------------------------------------------------------------ factory helper
    def build_all(self) -> List[BaseTool]:
        return [
            self.build_list_tool(),
            self.build_read_tool(),
            self.build_glob_tool(),
            self.build_grep_tool(),
        ]

