"""Configuration helpers for the real filesystem middleware."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

# Defaults align with architecture documentation
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_LIST_MAX_RESULTS = 1000
DEFAULT_GREP_MAX_RESULTS = 100
DEFAULT_GREP_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
_PROJECT_MARKERS = (".git", "pyproject.toml", "package.json")


def _auto_detect_project_root() -> Path:
    """Locate the project root by searching for common repository markers."""
    candidates: List[Path] = []
    cwd = Path.cwd().resolve()
    candidates.append(cwd)
    current = cwd
    while current != current.parent:
        candidates.append(current.parent)
        current = current.parent

    module_path = Path(__file__).resolve()
    candidates.append(module_path.parent)
    current = module_path.parent
    while current != current.parent:
        candidates.append(current.parent)
        current = current.parent

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if any((candidate / marker).exists() for marker in _PROJECT_MARKERS):
            return candidate
    return cwd


def _expand_placeholders(raw: str, *, project_root: Path, home: Path) -> str:
    """Expand ${VAR} placeholders using environment variables and known values."""

    def _replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token == "PROJECT_ROOT":
            return str(project_root)
        if token == "HOME":
            return str(home)
        return os.environ.get(token, match.group(0))

    return _PLACEHOLDER_PATTERN.sub(_replace, raw)


def _normalise_path(
    raw: str,
    *,
    project_root: Path,
) -> Path:
    """Convert a raw configuration path into an absolute normalised Path."""
    home = Path.home()
    expanded = _expand_placeholders(raw, project_root=project_root, home=home)
    expanded = os.path.expanduser(expanded)
    path = Path(expanded)
    if not path.is_absolute():
        path = project_root / path
    try:
        return path.resolve(strict=False)
    except FileNotFoundError:
        return path.absolute()


def _prepare_allowed_paths(entries: Sequence[str] | None, *, project_root: Path) -> tuple[Path, ...]:
    if entries is None:
        return (project_root,)
    if len(entries) == 0:
        return ()
    normalised = [_normalise_path(entry, project_root=project_root) for entry in entries]
    unique: List[Path] = []
    for candidate in normalised:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def _prepare_excluded_paths(entries: Sequence[str] | None, *, project_root: Path) -> tuple[Path, ...]:
    if not entries:
        return ()
    normalised = [_normalise_path(entry, project_root=project_root) for entry in entries]
    unique: List[Path] = []
    for candidate in normalised:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def _prepare_extensions(entries: Sequence[str] | None) -> tuple[str, ...]:
    if not entries:
        return (".txt", ".md", ".json", ".yaml", ".yml")
    cleaned: List[str] = []
    for entry in entries:
        normalized = entry.strip().lower()
        if not normalized:
            continue
        if normalized != "*" and not normalized.startswith("."):
            normalized = f".{normalized}"
        if normalized not in cleaned:
            cleaned.append(normalized)
    return tuple(cleaned)


@dataclass(slots=True)
class RealFilesystemSecurityOptions:
    allowed_paths: tuple[Path, ...]
    excluded_paths: tuple[Path, ...]
    allowed_extensions: tuple[str, ...]
    max_file_size: int


@dataclass(slots=True)
class RealFilesystemPerformanceOptions:
    list_max_results: int
    glob_max_results: int
    grep_max_results: int
    grep_max_file_size: int


@dataclass(slots=True)
class RealFilesystemAdvancedOptions:
    follow_symlinks: bool
    case_sensitive: bool
    ignore_hidden_files: bool


@dataclass(slots=True)
class RealFilesystemOptions:
    project_root: Path
    security: RealFilesystemSecurityOptions
    performance: RealFilesystemPerformanceOptions
    advanced: RealFilesystemAdvancedOptions

    def resolve_path(self, raw_path: str | None) -> Path:
        """Resolve a raw path string against the project root."""
        target = raw_path or str(self.project_root)
        return _normalise_path(target, project_root=self.project_root)

    def describe(self) -> Dict[str, Any]:
        """Return a serialisable summary of the configuration."""
        return {
            "project_root": str(self.project_root),
            "allowed_paths": [str(path) for path in self.security.allowed_paths],
            "excluded_paths": [str(path) for path in self.security.excluded_paths],
            "allowed_extensions": list(self.security.allowed_extensions),
            "max_file_size": self.security.max_file_size,
            "list_max_results": self.performance.list_max_results,
            "follow_symlinks": self.advanced.follow_symlinks,
            "case_sensitive": self.advanced.case_sensitive,
            "ignore_hidden_files": self.advanced.ignore_hidden_files,
        }


def build_real_filesystem_options(config: Dict[str, Any] | None) -> RealFilesystemOptions:
    """Create RealFilesystemOptions from raw configuration dictionary."""
    raw_config = config or {}
    project_root_value = raw_config.get("project_root") or "${AUTO_DETECT}"

    auto_root = _auto_detect_project_root()
    if isinstance(project_root_value, str) and project_root_value.strip() == "${AUTO_DETECT}":
        project_root = auto_root
    else:
        project_root = _normalise_path(str(project_root_value), project_root=auto_root)

    security_cfg = raw_config.get("security", {}) or {}
    performance_cfg = raw_config.get("performance", {}) or {}
    advanced_cfg = raw_config.get("advanced", {}) or {}

    allowed_paths = _prepare_allowed_paths(security_cfg.get("allowed_paths"), project_root=project_root)
    excluded_paths = _prepare_excluded_paths(security_cfg.get("excluded_paths"), project_root=project_root)
    allowed_extensions = _prepare_extensions(security_cfg.get("allowed_extensions"))
    max_file_size = int(security_cfg.get("max_file_size", DEFAULT_MAX_FILE_SIZE))

    security = RealFilesystemSecurityOptions(
        allowed_paths=allowed_paths,
        excluded_paths=excluded_paths,
        allowed_extensions=allowed_extensions,
        max_file_size=max_file_size,
    )

    performance = RealFilesystemPerformanceOptions(
        list_max_results=int(performance_cfg.get("glob_max_results", DEFAULT_LIST_MAX_RESULTS)),
        glob_max_results=int(performance_cfg.get("glob_max_results", DEFAULT_LIST_MAX_RESULTS)),
        grep_max_results=int(performance_cfg.get("grep_max_results", DEFAULT_GREP_MAX_RESULTS)),
        grep_max_file_size=int(performance_cfg.get("grep_max_file_size", DEFAULT_GREP_MAX_FILE_SIZE)),
    )

    advanced = RealFilesystemAdvancedOptions(
        follow_symlinks=bool(advanced_cfg.get("follow_symlinks", False)),
        case_sensitive=bool(advanced_cfg.get("case_sensitive", True)),
        ignore_hidden_files=bool(advanced_cfg.get("ignore_hidden_files", True)),
    )

    return RealFilesystemOptions(
        project_root=project_root,
        security=security,
        performance=performance,
        advanced=advanced,
    )
