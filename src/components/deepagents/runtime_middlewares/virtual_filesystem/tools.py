"""Tool implementations for virtual filesystem operations."""

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
    FilesystemState,
    VirtualFilesystemOptions,
)
from .utils import (
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

LIST_TOOL_NAME = "list_virtual_files"
READ_TOOL_NAME = "read_virtual_file"
WRITE_TOOL_NAME = "write_virtual_file"
EDIT_TOOL_NAME = "edit_virtual_file"
VIRTUAL_FILESYSTEM_TOOL_NAMES = (LIST_TOOL_NAME, READ_TOOL_NAME, WRITE_TOOL_NAME, EDIT_TOOL_NAME)


LIST_FILES_PROMPT = """List files in the virtual filesystem.

Call this first before reading or editing. Provide optional path to filter by directory."""

READ_FILE_PROMPT = """Read a file from the virtual filesystem with line numbers.

Use offset and limit for pagination when reading large files (e.g., offset=0, limit=500 for first 500 lines)."""

WRITE_FILE_PROMPT = """Create a new file in the virtual filesystem.

Target path must not exist. Follow path conventions: /workspace/tool_results/, /workspace/shared/, /workspace/processing/."""

EDIT_FILE_PROMPT = """Edit an existing file in the virtual filesystem.

Read the file first to ensure old_string matches exactly. Set replace_all=true to replace all occurrences."""


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
class VirtualFilesystemToolFactory:
    """Factory for creating virtual filesystem tools."""

    options: VirtualFilesystemOptions

    def classify_path(self, raw_path: str) -> PathLocation:
        """Classify path as either state or long-term storage.

        No security checks needed - virtual filesystem is isolated.
        """
        normalized = normalize_virtual_path(raw_path)
        if normalized.startswith(MEMORIES_PREFIX):
            if not self.options.long_term_memory:
                raise ValueError("Long-term filesystem paths are unavailable in the current configuration")
            stripped = normalize_virtual_path(_strip_memories_prefix(normalized))
            return PathLocation("long_term", stripped)
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
        file_data = string_to_file_data(content)  # No security parameter needed
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
        file_data = string_to_file_data(content)  # No security parameter needed
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
        updated = update_file_data(file_data, updated_content)  # No security parameter needed
        message = f"Replaced {occurrences if replace_all else 1} occurrence(s)"
        return updated, message

    def build_list_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or LIST_FILES_PROMPT

        @tool(LIST_TOOL_NAME, description=tool_description)
        def ls(
            runtime: ToolRuntime[None, FilesystemState],
            path: str | None = None,
        ) -> List[str] | str:
            # Wrap all operations in try-except to prevent conversation interruption
            try:
                state_files = self._list_files_from_state(runtime.state)
                long_term_files = self._list_files_from_store(runtime)
                combined = state_files + long_term_files
                return list_directory(combined, path)
            except ValueError as exc:
                # Return error message instead of raising exception
                return f"Error: {exc}"
            except Exception as exc:
                # Catch any unexpected errors
                return f"Error listing files: {exc}"

        return ls

    def build_read_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or READ_FILE_PROMPT

        @tool(READ_TOOL_NAME, description=tool_description)
        def read_file(
            file_path: str,
            runtime: ToolRuntime[None, FilesystemState],
            offset: int = DEFAULT_READ_OFFSET,
            limit: int = DEFAULT_READ_LIMIT,
        ) -> str:
            # Wrap all operations in try-except to prevent conversation interruption
            try:
                location = self.classify_path(file_path)
                if location.is_long_term:
                    file_data = self._fetch_file_from_store(runtime, location.path)
                else:
                    file_data = self._fetch_file_from_state(runtime.state, location.path)
                content_str = file_data_to_string(file_data)
                warning = empty_content_warning(content_str)
                if warning:
                    return warning
                lines = slice_content(file_data, offset=offset, limit=limit)
                return format_with_line_numbers(lines, start_line=offset + 1, style="tab")
            except ValueError as exc:
                # Return error message instead of raising exception
                return f"Error: {exc}"
            except Exception as exc:
                # Catch any unexpected errors
                return f"Error reading file '{file_path}': {exc}"

        return read_file

    def build_write_tool(self, description: str | None = None) -> BaseTool:
        tool_description = description or WRITE_FILE_PROMPT

        @tool(WRITE_TOOL_NAME, description=tool_description)
        def write_file(
            file_path: str,
            content: str,
            runtime: ToolRuntime[None, FilesystemState],
        ) -> Command | str:
            # Wrap all operations in try-except to prevent conversation interruption
            try:
                location = self.classify_path(file_path)
                if location.is_long_term:
                    return self._write_file_to_store(runtime, path=location.path, content=content)
                return self._write_file_to_state(runtime, path=location.path, content=content)
            except ValueError as exc:
                # Return error message instead of raising exception
                return f"Error: {exc}"
            except Exception as exc:
                # Catch any unexpected errors
                return f"Error writing file '{file_path}': {exc}"

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
            # Wrap all operations in try-except to prevent conversation interruption
            try:
                if not runtime.tool_call_id:
                    return "Error: Tool call ID missing while attempting to edit"

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
            except ValueError as exc:
                # Return error message instead of raising exception
                return f"Error: {exc}"
            except Exception as exc:
                # Catch any unexpected errors
                return f"Error editing file '{file_path}': {exc}"

        return edit_file

    def build_all(self) -> List[BaseTool]:
        return [
            self.build_list_tool(),
            self.build_read_tool(),
            self.build_write_tool(),
            self.build_edit_tool(),
        ]


def get_virtual_filesystem_tools(
    *,
    options: VirtualFilesystemOptions,
    descriptions: Optional[Sequence[str]] = None,
) -> List[BaseTool]:
    """Convenience helper to construct the virtual filesystem toolset."""
    factory = VirtualFilesystemToolFactory(options=options)
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
