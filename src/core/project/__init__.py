"""
Project-level context and metadata management.
"""

from .context import ProjectContext
from .detector import detect_project_root, is_iris_source_project
from .metadata import MetadataManager, ProjectMetadata, LastSessionInfo
from .share import IrisShareDir
from .paths import resolve_storage_path

__all__ = [
    "ProjectContext",
    "MetadataManager",
    "ProjectMetadata",
    "LastSessionInfo",
    "IrisShareDir",
    "detect_project_root",
    "is_iris_source_project",
    "resolve_storage_path",
]
