"""Security checks for the real filesystem middleware."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .config import RealFilesystemOptions


class RealFilesystemError(Exception):
    """Base error for real filesystem operations."""


class PathValidationError(RealFilesystemError):
    """Raised when a path fails security validation."""


class FileTypeNotAllowedError(PathValidationError):
    """Raised when a file extension is not permitted."""


class FileTooLargeError(RealFilesystemError):
    """Raised when attempting to read a file exceeding the size limit."""


class BinaryFileNotAllowedError(PathValidationError):
    """Raised when a binary file is encountered where text content is required."""


def _normalised(path: Path, *, case_sensitive: bool) -> str:
    text = path.as_posix()
    return text if case_sensitive else text.lower()


def _is_within(path: Path, candidates: Iterable[Path], *, case_sensitive: bool) -> bool:
    target = _normalised(path, case_sensitive=case_sensitive)
    for candidate in candidates:
        base = _normalised(candidate, case_sensitive=case_sensitive).rstrip("/")
        if target == base:
            return True
        if target.startswith(f"{base}/"):
            return True
    return False


def _contains_symlink(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except OSError:
        return False
    for parent in path.parents:
        if parent == parent.parent:
            break
        try:
            if parent.is_symlink():
                return True
        except OSError:
            continue
    return False


def _is_hidden(path: Path) -> bool:
    for part in path.parts:
        if part.startswith("."):
            return True
    return False


def _ensure_extension_allowed(path: Path, options: RealFilesystemOptions) -> None:
    """Raise if the file extension is disallowed under current security settings."""
    extensions = options.security.allowed_extensions
    if "*" in extensions:
        return
    suffix = path.suffix.lower()
    if suffix:
        if suffix not in extensions:
            raise FileTypeNotAllowedError(f"Extension '{suffix}' is not allowed for '{path}'")
    else:
        if "" not in extensions:
            raise FileTypeNotAllowedError(f"Files without an extension are not permitted: '{path}'")


def ensure_directory_access(
    path: Path,
    options: RealFilesystemOptions,
    *,
    enforce_excluded: bool = True,
) -> None:
    """Ensure a directory is reachable under the configured security rules."""
    case_sensitive = options.advanced.case_sensitive
    if not _is_within(path, options.security.allowed_paths, case_sensitive=case_sensitive):
        raise PathValidationError(f"Path '{path}' is outside the allowed directories")

    if enforce_excluded and options.security.excluded_paths and _is_within(
        path, options.security.excluded_paths, case_sensitive=case_sensitive
    ):
        raise PathValidationError(f"Path '{path}' is in the excluded directories list")

    if not options.advanced.follow_symlinks and _contains_symlink(path):
        raise PathValidationError(f"Symlink access is disabled: '{path}'")


def ensure_file_access(
    path: Path,
    options: RealFilesystemOptions,
    *,
    enforce_excluded: bool = True,
) -> None:
    """Ensure a file path satisfies access, extension, and size rules."""
    ensure_directory_access(
        path.parent if path.parent != Path(path.anchor) else path,
        options,
        enforce_excluded=enforce_excluded,
    )
    _ensure_extension_allowed(path, options)

    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise exc
    except OSError as exc:
        raise PathValidationError(f"Failed to read metadata for '{path}': {exc}") from exc

    if size > options.security.max_file_size:
        raise FileTooLargeError(
            f"File '{path}' is {size} bytes which exceeds the limit "
            f"of {options.security.max_file_size} bytes"
        )


def validate_directory(
    raw_path: str | None,
    options: RealFilesystemOptions,
    *,
    enforce_excluded: bool = True,
) -> Path:
    """Validate a directory path string and return the canonical Path."""
    path = options.resolve_path(raw_path)
    if not path.exists():
        raise PathValidationError(f"Directory does not exist: '{path}'")
    if not path.is_dir():
        raise PathValidationError(f"Expected directory path but got: '{path}'")
    ensure_directory_access(path, options, enforce_excluded=enforce_excluded)
    return path


def validate_file(
    raw_path: str,
    options: RealFilesystemOptions,
    *,
    enforce_excluded: bool = True,
) -> Path:
    """Validate a file path string and return the canonical Path."""
    path = options.resolve_path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: '{path}'")
    if not path.is_file():
        raise PathValidationError(f"Expected file path but got: '{path}'")
    ensure_file_access(path, options, enforce_excluded=enforce_excluded)
    return path


def validate_new_file_path(raw_path: str, options: RealFilesystemOptions) -> Path:
    """Validate a candidate path for creating or overwriting a file."""
    path = options.resolve_path(raw_path)
    parent = path.parent
    if not parent.exists():
        raise PathValidationError(f"Parent directory does not exist: '{parent}'")
    if not parent.is_dir():
        raise PathValidationError(f"Parent path is not a directory: '{parent}'")
    ensure_directory_access(parent, options, enforce_excluded=True)
    if path.exists():
        if path.is_dir():
            raise PathValidationError(f"Cannot write to directory path: '{path}'")
        if path.is_symlink() and not options.advanced.follow_symlinks:
            raise PathValidationError(f"Symlink access is disabled: '{path}'")
        _ensure_extension_allowed(path, options)
    else:
        _ensure_extension_allowed(path, options)
    return path


def is_hidden(path: Path) -> bool:
    """Public helper to determine if a path should be treated as hidden."""
    return _is_hidden(path)
