from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config
from langgraph.store.base import BaseStore, Item
from langgraph.types import Command

from .types import (
    DEFAULT_READ_LIMIT,
    DEFAULT_READ_OFFSET,
    MEMORIES_PREFIX,
    FileData,
    FilesystemOptions,
    FilesystemSecurity,
    FilesystemState,
)
from .utils import (
    assert_path_allowed,
    empty_content_warning,
    file_data_from_store_item,
    file_data_to_string,
    format_with_line_numbers,
    list_directory,
    normalize_virtual_path,
    slice_content,
    store_payload_from_file_data,
    string_to_file_data,
    update_file_data,
)

LIST_TOOL_NAME = "list_files"
READ_TOOL_NAME = "read_file"
WRITE_TOOL_NAME = "write_file"
EDIT_TOOL_NAME = "edit_file"
FILESYSTEM_TOOL_NAMES = (LIST_TOOL_NAME, READ_TOOL_NAME, WRITE_TOOL_NAME, EDIT_TOOL_NAME)


LIST_FILES_PROMPT = """Enumerate files available inside the virtual filesystem.

Usage guidelines:
- Call this tool before reading or editing to understand available files.
- Provide an optional absolute path to scope the results to a directory.
- Paths always start with '/' and use forward slashes."""

READ_FILE_PROMPT = """Render the contents of a file with line numbers.

Usage guidelines:
- File paths must be absolute.
- Reads up to 2000 lines by default; use offset and limit for pagination.
- Long lines are truncated for display but retained in storage."""

WRITE_FILE_PROMPT = """Create a brand-new file in the virtual filesystem.

Usage guidelines:
- The target path must not already exist; read or edit instead of overwriting.
- Provide the full contents of the file in a single call.
- Use this only when creating new files is explicitly required."""

EDIT_FILE_PROMPT = """Apply precise text replacements to an existing file.

Usage guidelines:
- Ensure the file has been read in the current conversation before editing.
- By default only the first occurrence is replaced; set replace_all=true otherwise.
- Strings must match the file contents exactly (after the line number prefix)."""


class PathLocation:
    """Helper describing whether a file lives in the transient state or long-term store."""

    def __init__(self, kind: str, path: str) -> None:
        self.kind = kind  # "state" or "long_term"
        self.path = path

    @property
    def is_long_term(self) -> bool:
        return self.kind == "long_term"

    @property
    def is_state(self) -> bool:
        return self.kind == "state"


def _namespace() -> Tuple[str, ...]:
    """Return the namespace tuple used for long-term storage."""
    namespace = "filesystem"
    config = get_config()
    if not config:
        return (namespace,)
    assistant_id = config.get("metadata", {}).get("assistant_id")
    if assistant_id:
        return (assistant_id, namespace)
    return (namespace,)


def _require_store(runtime: ToolRuntime[None, FilesystemState]) -> BaseStore:
    """Return runtime.store or raise if unavailable."""
    store = runtime.store
    if store is None:
        raise ValueError("Long-term memory is enabled but no store is attached to the runtime")
    return store


def _append_memories_prefix(path: str) -> str:
    return f"{MEMORIES_PREFIX}{path.lstrip('/')}"


def _strip_memories_prefix(path: str) -> str:
    if path.startswith(MEMORIES_PREFIX):
        remainder = path[len(MEMORIES_PREFIX) :]
        return "/" + remainder.lstrip("/")
    return path


@dataclass(slots=True)
class FilesystemToolFactory:
    options: FilesystemOptions

    @property
    def security(self) -> FilesystemSecurity:
        return self.options.security

    def classify_path(self, raw_path: str) -> PathLocation:
        normalized = normalize_virtual_path(raw_path)
        if normalized.startswith(MEMORIES_PREFIX):
            if not self.options.long_term_memory:
                raise ValueError("Long-term filesystem paths are unavailable in the current configuration")
            stripped = normalize_virtual_path(_strip_memories_prefix(normalized))
            return PathLocation("long_term", stripped)
        assert_path_allowed(normalized, self.security)
        return PathLocation("state", normalized)

    def _list_files_from_state(self, state: FilesystemState) -> List[str]:
        files = state.get("files")
        if not files:
            return []
        return sorted(files.keys())

    def _list_files_from_store(self, runtime: ToolRuntime[None, FilesystemState]) -> List[str]:
        if not self.options.long_term_memory:
            return []
        store = _require_store(runtime)
        namespace = _namespace()
        items = store.search(namespace)
        if not items:
            return []

        def item_key(record: Item | dict[str, Any]) -> str:
            if isinstance(record, Item):
                return record.key
            return record["key"]

        return sorted(_append_memories_prefix(item_key(item)) for item in items)

    def _fetch_file_from_state(self, state: FilesystemState, path: str) -> FileData:
        files = state.get("files") or {}
        try:
            return files[path]
        except KeyError as exc:
            raise ValueError(f"File '{path}' not found") from exc

    def _fetch_file_from_store(self, runtime: ToolRuntime[None, FilesystemState], path: str) -> FileData:
        store = _require_store(runtime)
        namespace = _namespace()
        item = store.get(namespace, path)
        if item is None:
            raise ValueError(f"File '{_append_memories_prefix(path)}' not found")
        return file_data_from_store_item(item)

    def _write_file_to_state(
        self,
        runtime: ToolRuntime[None, FilesystemState],
        *,
        path: str,
        content: str,
    ) -> Command | str:
        files = runtime.state.get("files", {})
        if path in files:
            return (
                "Cannot create file because it already exists. "
                "Read the file and use the edit tool instead."
            )
        file_data = string_to_file_data(content, security=self.security)
        if not runtime.tool_call_id:
            raise ValueError("Tool call ID missing while attempting to write")
        update = {
            "files": {path: file_data},
            "messages": [
                ToolMessage(f"Created file {path}", tool_call_id=runtime.tool_call_id)
            ],
        }
        return Command(update=update)

    def _write_file_to_store(
        self,
        runtime: ToolRuntime[None, FilesystemState],
        *,
        path: str,
        content: str,
    ) -> str:
        store = _require_store(runtime)
        namespace = _namespace()
        if store.get(namespace, path) is not None:
            return (
                "Cannot create file because it already exists in long-term storage. "
                "Read the file and edit it instead."
            )
        file_data = string_to_file_data(content, security=self.security)
        store.put(namespace, path, store_payload_from_file_data(file_data))
        return f"Stored file {_append_memories_prefix(path)} in long-term memory"

    def _edit_file_content(
        self,
        file_data: FileData,
        *,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> tuple[FileData, str] | str:
        if not old_string:
            return "The old_string parameter cannot be empty"
        occurrences = file_data_to_string(file_data).count(old_string)
        if occurrences == 0:
            return f"Did not find '{old_string}' in the file"
        if occurrences > 1 and not replace_all:
            return (
                f"Found {occurrences} matches for '{old_string}'. "
                "Set replace_all=true or provide more context."
            )
        updated_content = file_data_to_string(file_data).replace(
            old_string,
            new_string,
            occurrences if replace_all else 1,
        )
        updated = update_file_data(file_data, updated_content, security=self.security)
        message = f"Replaced {occurrences if replace_all else 1} occurrence(s)"
        return updated, message

    def build_list_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or LIST_FILES_PROMPT

        @tool(LIST_TOOL_NAME, description=tool_description)
        def list_files(
            runtime: ToolRuntime[None, FilesystemState],
            path: str | None = None,
        ) -> List[str]:
            state_files = self._list_files_from_state(runtime.state)
            long_term_files = self._list_files_from_store(runtime)
            combined = state_files + long_term_files
            return list_directory(combined, path)

        return list_files

    def build_read_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or READ_FILE_PROMPT

        @tool(READ_TOOL_NAME, description=tool_description)
        def read_file(
            file_path: str,
            runtime: ToolRuntime[None, FilesystemState],
            offset: int = DEFAULT_READ_OFFSET,
            limit: int = DEFAULT_READ_LIMIT,
        ) -> str:
            location = self.classify_path(file_path)
            if location.is_long_term:
                file_data = self._fetch_file_from_store(runtime, location.path)
            else:
                assert_path_allowed(location.path, self.security)
                file_data = self._fetch_file_from_state(runtime.state, location.path)
            content_str = file_data_to_string(file_data)
            warning = empty_content_warning(content_str)
            if warning:
                return warning
            try:
                lines = slice_content(file_data, offset=offset, limit=limit)
            except ValueError as exc:
                return str(exc)
            return format_with_line_numbers(lines, start_line=offset + 1, style="tab")

        return read_file

    def build_write_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or WRITE_FILE_PROMPT

        @tool(WRITE_TOOL_NAME, description=tool_description)
        def write_file(
            file_path: str,
            content: str,
            runtime: ToolRuntime[None, FilesystemState],
        ) -> Command | str:
            location = self.classify_path(file_path)
            if location.is_long_term:
                return self._write_file_to_store(runtime, path=location.path, content=content)
            assert_path_allowed(location.path, self.security)
            return self._write_file_to_state(runtime, path=location.path, content=content)

        return write_file

    def build_edit_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or EDIT_FILE_PROMPT

        @tool(EDIT_TOOL_NAME, description=tool_description)
        def edit_file(
            file_path: str,
            old_string: str,
            new_string: str,
            runtime: ToolRuntime[None, FilesystemState],
            replace_all: bool = False,
        ) -> Command | str:
            if not runtime.tool_call_id:
                raise ValueError("Tool call ID missing while attempting to edit")

            location = self.classify_path(file_path)
            if location.is_long_term:
                store = _require_store(runtime)
                namespace = _namespace()
                try:
                    file_data = self._fetch_file_from_store(runtime, location.path)
                except ValueError as exc:
                    return str(exc)
                edit_result = self._edit_file_content(
                    file_data,
                    old_string=old_string,
                    new_string=new_string,
                    replace_all=replace_all,
                )
                if isinstance(edit_result, str):
                    return edit_result
                updated, message = edit_result
                store.put(namespace, location.path, store_payload_from_file_data(updated))
                return message

            assert_path_allowed(location.path, self.security)
            try:
                file_data = self._fetch_file_from_state(runtime.state, location.path)
            except ValueError as exc:
                return str(exc)
            edit_result = self._edit_file_content(
                file_data,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
            )
            if isinstance(edit_result, str):
                return edit_result
            updated, message = edit_result
            update = {
                "files": {location.path: updated},
                "messages": [
                    ToolMessage(f"{message} in {location.path}", tool_call_id=runtime.tool_call_id)
                ],
            }
            return Command(update=update)

        return edit_file

    def build_all(self) -> List[BaseTool]:
        return [
            self.build_list_tool(),
            self.build_read_tool(),
            self.build_write_tool(),
            self.build_edit_tool(),
        ]


def get_filesystem_tools(
    *,
    options: FilesystemOptions,
    descriptions: Optional[Sequence[str]] = None,
) -> List[BaseTool]:
    """Convenience helper to construct the filesystem toolset."""
    factory = FilesystemToolFactory(options=options)
    if descriptions is None:
        return factory.build_all()

    description_map = list(descriptions)
    tools: List[BaseTool] = []
    builders = [
        factory.build_list_tool,
        factory.build_read_tool,
        factory.build_write_tool,
        factory.build_edit_tool,
    ]
    for builder, override in zip(builders, description_map, strict=False):
        tools.append(builder(override))
    # If fewer overrides are provided, use defaults for the rest.
    for builder in builders[len(description_map) :]:
        tools.append(builder())
    return tools
