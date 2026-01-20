from pathlib import Path

from .context import ProjectContext


def resolve_storage_path(mode: str, project_context: ProjectContext) -> Path:
    """Helper to resolve a storage directory for a given mode using ProjectContext."""
    return project_context.get_storage_dir(mode)
