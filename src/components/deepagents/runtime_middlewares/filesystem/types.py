from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Dict, Iterable, List, Optional

from langchain.agents.middleware.types import AgentState
from typing_extensions import NotRequired, TypedDict

UTC = getattr(datetime, "UTC", timezone.utc)

MEMORIES_PREFIX = "/memories/"
EMPTY_CONTENT_WARNING = "System reminder: File exists but has empty contents"
MAX_LINE_LENGTH = 2000
LINE_NUMBER_WIDTH = 6
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 2000
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILE_LINES = 50_000


class FileData(TypedDict):
    """Serialized representation of a virtual file."""

    content: List[str]
    created_at: str
    modified_at: str


def _file_data_reducer(
    current: Dict[str, FileData] | None, updates: Dict[str, FileData | None]
) -> Dict[str, FileData]:
    """Merge filesystem updates while respecting deletion markers."""
    if current is None:
        return {path: data for path, data in updates.items() if data is not None}

    merged: Dict[str, FileData] = dict(current)
    for path, data in updates.items():
        if data is None:
            merged.pop(path, None)
        else:
            merged[path] = data
    return merged


class FilesystemState(AgentState):
    """LangGraph state schema for the virtual filesystem."""

    files: Annotated[NotRequired[Dict[str, FileData]], _file_data_reducer]


def iso_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class FilesystemSecurity:
    """Security configuration used to validate file operations."""

    allowed_paths: Iterable[str] = field(default_factory=list)
    excluded_paths: Iterable[str] = field(default_factory=list)
    excluded_extensions: Iterable[str] = field(default_factory=list)
    max_file_size: int = MAX_FILE_SIZE
    max_file_lines: int = MAX_FILE_LINES


@dataclass(slots=True)
class FilesystemOptions:
    """Runtime options controlling middleware behaviour."""

    long_term_memory: bool = False
    tool_token_limit_before_evict: Optional[int] = None
    security: FilesystemSecurity = field(default_factory=FilesystemSecurity)
