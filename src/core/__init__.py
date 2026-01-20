"""
Core module for shared components across the application.
"""

# Re-export project context utilities for convenience
from src.core.project import (  # noqa: F401
    ProjectContext,
    MetadataManager,
    ProjectMetadata,
    LastSessionInfo,
    IrisShareDir,
    detect_project_root,
    is_iris_source_project,
    resolve_storage_path,
)
