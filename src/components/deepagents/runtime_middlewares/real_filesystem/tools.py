"""Tool implementations for the real filesystem middleware."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import BaseTool, tool

from .config import RealFilesystemOptions
from .security import (
    BinaryFileNotAllowedError,
    FileTooLargeError,
    PathValidationError,
    RealFilesystemError,
    ensure_directory_access,
    ensure_file_access,
    validate_directory,
    validate_file,
    validate_new_file_path,
)
from .utils import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    EMPTY_CONTENT_WARNING,
    compute_text_diff,
    count_lines,
    encode_size,
    format_with_line_numbers,
    is_hidden_path,
    relative_display_path,
)

LIST_TOOL_NAME = "list_real_files"
READ_TOOL_NAME = "read_real_file"
WRITE_TOOL_NAME = "write_real_file"
EDIT_TOOL_NAME = "edit_real_file"
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

WRITE_PROMPT = """Write text content to a file on the host machine.

Triggers approval workflow with diff preview. Paths must stay within allowlist and use permitted extensions."""

EDIT_PROMPT = """Apply find-and-replace edits to a file on the host machine.

Triggers approval workflow with diff preview. Always read the file first to ensure old_string matches exactly."""

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

    def _is_builtin_skill_path(self, raw_path: str) -> bool:
        """
        Return True when a path is under built-in skills directory.

        This allows read operations to bypass generic excluded paths while still
        keeping write protection enforced by normal security checks.
        """
        try:
            from src.components.shared.skills.types import BUILT_IN_SKILLS_DIR

            candidate = self.options.resolve_path(raw_path)
            built_in_root = BUILT_IN_SKILLS_DIR.resolve(strict=False)
            resolved_candidate = candidate.resolve(strict=False)
            return resolved_candidate == built_in_root or built_in_root in resolved_candidate.parents
        except Exception:  # pylint: disable=broad-except
            return False

    @staticmethod
    def _coerce_encoding(encoding: str | None) -> str:
        """Normalise encoding names and ensure they are supported."""
        candidate = (encoding or "utf-8").strip() or "utf-8"
        try:
            "".encode(candidate)
        except LookupError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unsupported encoding '{candidate}'") from exc
        return candidate

    def _read_text(self, path: Path, *, encoding: str) -> str:
        """Read text content from disk enforcing the configured encoding."""
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            raise BinaryFileNotAllowedError(
                f"File '{path}' cannot be decoded using encoding '{encoding}'. Binary files are not supported."
            ) from exc
        except OSError as exc:
            raise RealFilesystemError(f"Failed to read '{path}': {exc}") from exc

    def _write_text(self, path: Path, content: str, *, encoding: str) -> None:
        """Persist text content to disk using the requested encoding."""
        try:
            path.write_text(content, encoding=encoding)
        except UnicodeEncodeError as exc:
            raise RealFilesystemError(
                f"Content cannot be encoded using '{encoding}': {exc}"
            ) from exc
        except OSError as exc:
            raise RealFilesystemError(f"Failed to write '{path}': {exc}") from exc

    def _ensure_content_size(self, content: str, *, encoding: str) -> None:
        """Ensure content size stays within configured security limits."""
        byte_length = encode_size(content, encoding)
        max_size = self.options.security.max_file_size
        if byte_length > max_size:
            raise RealFilesystemError(
                f"Content is {byte_length} bytes which exceeds the limit of {max_size} bytes."
            )

    @staticmethod
    def _perform_string_replacement(
        content: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> tuple[str, int] | str:
        """Replace occurrences of old_string within content."""
        if not old_string:
            return "old_string must not be empty."
        occurrences = content.count(old_string)
        if occurrences == 0:
            return "old_string was not found in the file."
        if replace_all:
            return content.replace(old_string, new_string), occurrences
        return content.replace(old_string, new_string, 1), 1

    def _try_ripgrep_search(
        self,
        pattern: str,
        base_dir: Path,
        file_pattern: str | None,
        case_sensitive: bool,
        context_lines: int,
        limit: int,
        include_hidden: bool,
    ) -> str | None:
        """Try to use ripgrep for fast searching. Returns None if ripgrep is unavailable.

        This method implements the performance optimization strategy by using ripgrep
        as the primary search engine, falling back to Python if unavailable.
        Follows YAGNI by only adding complexity where needed (performance-critical path).
        """
        cmd = ["rg", "--json", "--no-heading"]

        if not case_sensitive:
            cmd.append("-i")

        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])

        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        if not include_hidden:
            cmd.append("--hidden")

        cmd.extend(["--max-count", str(limit)])
        cmd.extend(["--", pattern, str(base_dir)])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return None

        if proc.returncode not in (0, 1):
            return None

        return self._parse_ripgrep_json_output(proc.stdout, limit)

    def _parse_ripgrep_json_output(self, json_output: str, limit: int) -> str:
        """Parse ripgrep JSON output into formatted string with line numbers.

        Follows DRY by reusing the same output format as Python implementation.
        """
        import json as json_lib

        matches: List[str] = []
        current_file: str | None = None
        file_matches: Dict[str, List[tuple[int, str]]] = {}

        for line in json_output.splitlines():
            if not line.strip():
                continue

            try:
                data = json_lib.loads(line)
            except json_lib.JSONDecodeError:
                continue

            if data.get("type") != "match":
                continue

            match_data = data.get("data", {})
            path_data = match_data.get("path", {})
            file_path = path_data.get("text")

            if not file_path:
                continue

            line_number = match_data.get("line_number")
            line_text = match_data.get("lines", {}).get("text", "").rstrip("\n")

            if line_number is None:
                continue

            try:
                relative_path = relative_display_path(Path(file_path), self.options.project_root)
            except (ValueError, OSError):
                relative_path = file_path

            if relative_path not in file_matches:
                file_matches[relative_path] = []

            file_matches[relative_path].append((int(line_number), line_text))

            if len(file_matches) * 10 >= limit:
                break

        for file_path, lines in file_matches.items():
            if len(matches) >= limit:
                break

            lines.sort(key=lambda x: x[0])

            for line_num, line_text in lines:
                if len(matches) >= limit:
                    break

                formatted_lines = format_with_line_numbers([line_text], start_line=line_num)
                header = f"# {file_path}:{line_num}"
                matches.append(f"{header}\n{formatted_lines}")

        if not matches:
            return "No matches found."

        return "\n\n".join(matches)

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
                ignore_excluded = self._is_builtin_skill_path(file_path)
                path = validate_file(
                    file_path,
                    self.options,
                    enforce_excluded=not ignore_excluded,
                )
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

    # ------------------------------------------------------------------ write tool
    def build_write_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or WRITE_PROMPT

        @tool(WRITE_TOOL_NAME, description=prompt)
        def write_real_file(
            file_path: str,
            content: str,
            encoding: str = "utf-8",
        ) -> str:
            try:
                normalised_encoding = self._coerce_encoding(encoding)
            except ValueError as exc:
                return str(exc)

            try:
                path = validate_new_file_path(file_path, self.options)
            except (PathValidationError, RealFilesystemError) as exc:
                return str(exc)

            existed = path.exists()
            previous_content = ""
            if existed:
                try:
                    ensure_file_access(path, self.options)
                except (PathValidationError, RealFilesystemError, FileNotFoundError) as exc:
                    return str(exc)
                try:
                    previous_content = self._read_text(path, encoding=normalised_encoding)
                except (BinaryFileNotAllowedError, RealFilesystemError) as exc:
                    return str(exc)

            try:
                self._ensure_content_size(content, encoding=normalised_encoding)
            except RealFilesystemError as exc:
                return str(exc)

            display_path = relative_display_path(path, self.options.project_root)
            diff_info = compute_text_diff(previous_content, content, display_path)

            try:
                self._write_text(path, content, encoding=normalised_encoding)
            except RealFilesystemError as exc:
                return str(exc)

            # TODO: persist operation details for session auditing once storage is available.

            result = {
                "status": "success",
                "path": display_path,
                "encoding": normalised_encoding,
                "overwritten": existed,
                "bytes_written": encode_size(content, normalised_encoding),
                "lines_written": count_lines(content),
                "diff": diff_info.diff,
                "diff_stats": {"added": diff_info.added_lines, "removed": diff_info.removed_lines},
                "diff_truncated": diff_info.truncated,
            }

            import json
            return json.dumps(result, ensure_ascii=False, indent=2)

        return write_real_file

    # ------------------------------------------------------------------ edit tool
    def build_edit_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or EDIT_PROMPT

        @tool(EDIT_TOOL_NAME, description=prompt)
        def edit_real_file(
            file_path: str,
            old_string: str,
            new_string: str,
            encoding: str = "utf-8",
            replace_all: bool = False,
        ) -> str:
            try:
                normalised_encoding = self._coerce_encoding(encoding)
            except ValueError as exc:
                return str(exc)

            try:
                path = validate_file(file_path, self.options)
            except FileNotFoundError as exc:
                return str(exc)
            except (PathValidationError, RealFilesystemError) as exc:
                return str(exc)

            try:
                current_content = self._read_text(path, encoding=normalised_encoding)
            except (BinaryFileNotAllowedError, RealFilesystemError) as exc:
                return str(exc)

            replacement = self._perform_string_replacement(
                current_content,
                old_string,
                new_string,
                replace_all,
            )
            if isinstance(replacement, str):
                return replacement

            updated_content, occurrences = replacement

            try:
                self._ensure_content_size(updated_content, encoding=normalised_encoding)
            except RealFilesystemError as exc:
                return str(exc)

            display_path = relative_display_path(path, self.options.project_root)
            diff_info = compute_text_diff(current_content, updated_content, display_path)

            try:
                self._write_text(path, updated_content, encoding=normalised_encoding)
            except RealFilesystemError as exc:
                return str(exc)

            # TODO: persist operation details for session auditing once storage is available.

            result = {
                "status": "success",
                "path": display_path,
                "encoding": normalised_encoding,
                "occurrences": occurrences,
                "bytes_written": encode_size(updated_content, normalised_encoding),
                "lines_written": count_lines(updated_content),
                "diff": diff_info.diff,
                "diff_stats": {"added": diff_info.added_lines, "removed": diff_info.removed_lines},
                "diff_truncated": diff_info.truncated,
            }

            import json
            return json.dumps(result, ensure_ascii=False, indent=2)

        return edit_real_file

    # ------------------------------------------------------------------ glob tool
    def build_glob_tool(self, description: str | None = None) -> BaseTool:
        prompt = description or GLOB_PROMPT

        @tool(GLOB_TOOL_NAME, description=prompt)
        def glob_real_files(
            pattern: str,
            base_path: str | None = None,
            recursive: bool = True,
            include_hidden: bool = False,
            include_metadata: bool = True,
        ) -> str:
            """Search for files using glob patterns with optional metadata.

            Args:
                pattern: Glob pattern (supports **, *, ?, character sets)
                base_path: Base directory to search (defaults to project root)
                recursive: Use recursive search (rglob)
                include_hidden: Include hidden files
                include_metadata: Include file size and modification time

            Returns:
                Formatted string with file paths and metadata
            """
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

                    display_path = relative_display_path(path, self.options.project_root)

                    if include_metadata:
                        try:
                            stat_info = path.stat()
                            size_bytes = stat_info.st_size
                            modified_timestamp = stat_info.st_mtime

                            if size_bytes >= 1024 * 1024:
                                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                            elif size_bytes >= 1024:
                                size_str = f"{size_bytes / 1024:.2f} KB"
                            else:
                                size_str = f"{size_bytes} bytes"

                            modified_str = datetime.fromtimestamp(modified_timestamp).strftime("%Y-%m-%d %H:%M:%S")

                            results.append(f"{display_path:60} | {size_str:12} | {modified_str}")
                        except OSError:
                            results.append(display_path)
                    else:
                        results.append(display_path)

                    if len(results) >= max_items:
                        truncated = True
                        break
            except OSError as exc:
                return f"Failed to search '{base_dir}': {exc}"

            if not results:
                return "No files matched the pattern."

            header = ""
            if include_metadata:
                header = f"{'Path':<60} | {'Size':>12} | Modified\n{'-' * 60} | {'-' * 12} | {'-' * 19}\n"

            output = header + "\n".join(results)

            if truncated:
                output += f"\n... truncated at {max_items} results"

            return output

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

            configured_limit = max(1, self.options.performance.grep_max_results)
            requested_limit = max_results if max_results is not None else configured_limit
            limit = max(1, min(requested_limit, configured_limit))

            # Try ripgrep first for performance (10-100x faster)
            ripgrep_result = self._try_ripgrep_search(
                pattern=pattern,
                base_dir=base_dir,
                file_pattern=file_pattern,
                case_sensitive=case_sensitive,
                context_lines=context_lines,
                limit=limit,
                include_hidden=include_hidden,
            )
            if ripgrep_result is not None:
                return ripgrep_result

            # Fallback to Python implementation
            search_glob = file_pattern or "**/*"
            iterator = base_dir.rglob(search_glob)
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
            self.build_write_tool(),
            self.build_edit_tool(),
            self.build_glob_tool(),
            self.build_grep_tool(),
        ]
