"""Preview helpers for Human-in-the-Loop approvals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.components.deepagents.runtime_middlewares.real_filesystem.utils import (
    compute_text_diff,
    count_lines,
    encode_size,
    relative_display_path,
)


@dataclass(slots=True)
class ApprovalPreview:
    """Structured information describing a pending tool action."""

    title: str
    details: List[str]
    diff: Optional[str] = None
    diff_title: Optional[str] = None
    diff_truncated: bool = False
    warning: Optional[str] = None
    error: Optional[str] = None


def _resolve_path(path_str: str) -> Path:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    return (Path.cwd() / candidate).resolve()


def _read_text(path: Path, encoding: str) -> str | str:
    try:
        return path.read_text(encoding=encoding)
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        return (
            f"File '{path}' cannot be decoded with encoding '{encoding}'. "
            "Binary files are not supported."
        )
    except LookupError:
        return f"Unsupported encoding '{encoding}'"
    except OSError as exc:
        return f"Failed to read '{path}': {exc}"


def _perform_string_replacement(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool,
) -> tuple[str, int] | str:
    if not old_string:
        return "old_string must not be empty."
    occurrences = content.count(old_string)
    if occurrences == 0:
        return "old_string was not found in the file."
    if replace_all:
        return content.replace(old_string, new_string), occurrences
    return content.replace(old_string, new_string, 1), 1


def _build_write_preview(args: Dict[str, Any]) -> ApprovalPreview | None:
    file_path = str(args.get("file_path") or "")
    if not file_path:
        return None
    encoding = str(args.get("encoding") or "utf-8")
    content = str(args.get("content", ""))

    physical_path = _resolve_path(file_path)
    existing_content = _read_text(physical_path, encoding)
    if isinstance(existing_content, str) and existing_content.startswith("Failed to read"):
        return ApprovalPreview(
            title=f"Write {file_path}",
            details=[f"File: {file_path}", "Action: Write text file"],
            error=existing_content,
        )
    if isinstance(existing_content, str) and existing_content.startswith("Unsupported encoding"):
        return ApprovalPreview(
            title=f"Write {file_path}",
            details=[f"File: {file_path}", "Action: Write text file"],
            error=existing_content,
        )
    if isinstance(existing_content, str) and existing_content.startswith("File '") and "Binary" in existing_content:
        return ApprovalPreview(
            title=f"Write {file_path}",
            details=[f"File: {file_path}", "Action: Write text file"],
            error=existing_content,
        )

    previous = "" if existing_content is None else str(existing_content)
    display_path = relative_display_path(physical_path, Path.cwd())
    diff_info = compute_text_diff(previous, content, display_path)
    details = [
        f"File: {file_path}",
        "Action: Overwrite existing file" if physical_path.exists() else "Action: Create new file",
        f"Encoding: {encoding}",
        f"Lines after write: {count_lines(content)}",
        f"Bytes to write: {encode_size(content, encoding)}",
    ]
    preview = ApprovalPreview(
        title=f"Write {display_path}",
        details=details,
        diff=diff_info.diff,
        diff_title=f"Diff {display_path}" if diff_info.diff else None,
        diff_truncated=diff_info.truncated,
    )
    if diff_info.truncated:
        preview.warning = "Diff preview truncated to safety limit."
    return preview


def _build_edit_preview(args: Dict[str, Any]) -> ApprovalPreview | None:
    file_path = str(args.get("file_path") or "")
    if not file_path:
        return None
    encoding = str(args.get("encoding") or "utf-8")
    old_string = str(args.get("old_string", ""))
    new_string = str(args.get("new_string", ""))
    replace_all = bool(args.get("replace_all", False))

    physical_path = _resolve_path(file_path)
    existing_content = _read_text(physical_path, encoding)
    if isinstance(existing_content, str) and existing_content.startswith("Failed to read"):
        return ApprovalPreview(
            title=f"Edit {file_path}",
            details=[f"File: {file_path}", "Action: Replace text"],
            error=existing_content,
        )
    if isinstance(existing_content, str) and existing_content.startswith("Unsupported encoding"):
        return ApprovalPreview(
            title=f"Edit {file_path}",
            details=[f"File: {file_path}", "Action: Replace text"],
            error=existing_content,
        )
    if isinstance(existing_content, str) and existing_content.startswith("File '") and "Binary" in existing_content:
        return ApprovalPreview(
            title=f"Edit {file_path}",
            details=[f"File: {file_path}", "Action: Replace text"],
            error=existing_content,
        )

    previous = str(existing_content or "")
    replacement = _perform_string_replacement(previous, old_string, new_string, replace_all)
    if isinstance(replacement, str):
        return ApprovalPreview(
            title=f"Edit {file_path}",
            details=[f"File: {file_path}", "Action: Replace text"],
            error=replacement,
        )

    updated_content, occurrences = replacement
    display_path = relative_display_path(physical_path, Path.cwd())
    diff_info = compute_text_diff(previous, updated_content, display_path)

    details = [
        f"File: {file_path}",
        f"Action: Replace text ({'all occurrences' if replace_all else 'single occurrence'})",
        f"Occurrences matched: {occurrences}",
        f"Bytes after edit: {encode_size(updated_content, encoding)}",
    ]
    preview = ApprovalPreview(
        title=f"Edit {display_path}",
        details=details,
        diff=diff_info.diff,
        diff_title=f"Diff {display_path}" if diff_info.diff else None,
        diff_truncated=diff_info.truncated,
    )
    if diff_info.truncated:
        preview.warning = "Diff preview truncated to safety limit."
    return preview


def _build_shell_preview(args: Dict[str, Any]) -> ApprovalPreview | None:
    command = str(args.get("command") or args.get("input") or "")
    if not command:
        return None
    timeout = args.get("timeout")
    env_overrides = args.get("env") or {}

    details = [
        f"Command: {command}",
        f"Working directory: {Path.cwd()}",
    ]
    if timeout:
        details.append(f"Timeout: {timeout} seconds")
    if env_overrides:
        keys = sorted(str(key) for key in env_overrides.keys())
        details.append(f"Environment overrides: {', '.join(keys)}")

    return ApprovalPreview(
        title="Execute Shell Command",
        details=details,
    )


def build_approval_preview(tool_name: str, args: Dict[str, Any] | None) -> ApprovalPreview | None:
    """Return a HITL preview for supported tools."""
    if not args:
        return None
    if tool_name == "write_real_file":
        return _build_write_preview(args)
    if tool_name == "edit_real_file":
        return _build_edit_preview(args)
    if tool_name == "execute_shell":
        return _build_shell_preview(args)
    return None
