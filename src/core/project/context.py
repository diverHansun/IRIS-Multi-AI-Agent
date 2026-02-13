from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .detector import detect_project_root, is_iris_source_project


@dataclass
class ProjectContext:
    """Project context holding resolved paths and identifiers."""

    project_path: Path
    project_id: str
    project_name: str
    is_iris_source: bool = False

    @classmethod
    def from_cwd(cls) -> "ProjectContext":
        """Build context from current working directory."""
        return cls.from_path(Path.cwd())

    @classmethod
    def from_path(cls, path: Path) -> "ProjectContext":
        """Build context from an explicit path, detecting project root if possible."""
        project_root = detect_project_root(path)
        if project_root is None:
            project_root = path.resolve()

        project_name = project_root.name
        project_id = cls._generate_project_id(project_root)
        is_iris = is_iris_source_project(project_root)

        return cls(
            project_path=project_root,
            project_id=project_id,
            project_name=project_name,
            is_iris_source=is_iris,
        )

    @staticmethod
    def _generate_project_id(project_path: Path) -> str:
        """Generate stable id {safe_dir}_{hash8} for a project path."""
        path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
        dir_name = project_path.name
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", dir_name)
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        return f"{safe_name}_{path_hash}"

    @property
    def iris_dir(self) -> Path:
        return self.project_path / ".iris"

    @property
    def config_file(self) -> Path:
        return self.iris_dir / "config.json"

    @property
    def agent_md_file(self) -> Path:
        return self.iris_dir / "agent.md"

    @property
    def skills_dir(self) -> Path:
        """Project-level skills directory (<project>/.iris/skills/)."""
        return self.iris_dir / "skills"

    def get_storage_dir(self, mode: str) -> Path:
        """
        Resolve storage directory for a mode.
        Accepted modes: "llm", "basic", "deep" plus raw dir names for compatibility.
        """
        mode_dir_map = {
            "llm": "llm",
            "basic": "basicagent",
            "basicagent": "basicagent",
            "deep": "deepagent",
            "deepagent": "deepagent",
        }
        dir_name = mode_dir_map.get(mode, mode)
        return self.iris_dir / "sessions" / dir_name

    def ensure_structure(self) -> None:
        """Create .iris and session subdirectories if missing."""
        for mode in ("llm", "basicagent", "deepagent"):
            (self.iris_dir / "sessions" / mode).mkdir(parents=True, exist_ok=True)

    def get_storage_dirs_dict(self) -> dict[str, str]:
        """Return mapping compatible with SessionManager."""
        return {
            "llm": str(self.get_storage_dir("llm")),
            "basic": str(self.get_storage_dir("basic")),
            "deep": str(self.get_storage_dir("deep")),
        }
