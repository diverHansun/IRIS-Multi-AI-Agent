from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .share import IrisShareDir

logger = logging.getLogger(__name__)


@dataclass
class LastSessionInfo:
    mode: str
    session_id: str


@dataclass
class ProjectMetadata:
    path: str
    id: str
    name: str
    last_session: Optional[LastSessionInfo] = None
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.last_session:
            data["last_session"] = asdict(self.last_session)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMetadata":
        last_session = None
        if data.get("last_session"):
            last_session = LastSessionInfo(**data["last_session"])
        return cls(
            path=data["path"],
            id=data["id"],
            name=data["name"],
            last_session=last_session,
            last_used=data.get("last_used", datetime.now().isoformat()),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class MetadataManager:
    """Manage ~/.iris/metadata.json with basic CRUD helpers."""

    VERSION = "1.0"

    def __init__(self, metadata_file: Optional[Path] = None):
        self.metadata_file = metadata_file or IrisShareDir.get_metadata_file()
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.metadata_file.exists():
            return {"version": self.VERSION, "projects": []}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Failed to load metadata: %s", exc)
            return {"version": self.VERSION, "projects": []}

    def _save(self) -> None:
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("Failed to save metadata: %s", exc)

    def get_project(self, project_path: Path) -> Optional[ProjectMetadata]:
        path_str = str(project_path.resolve())
        for proj in self._data.get("projects", []):
            if proj.get("path") == path_str:
                return ProjectMetadata.from_dict(proj)
        return None

    def update_project(
        self,
        project_path: Path,
        project_id: str,
        project_name: str,
        mode: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        path_str = str(project_path.resolve())
        now = datetime.now().isoformat()
        projects = self._data.get("projects", [])
        existing_idx = None
        for idx, proj in enumerate(projects):
            if proj.get("path") == path_str:
                existing_idx = idx
                break

        if existing_idx is not None:
            meta = ProjectMetadata.from_dict(projects[existing_idx])
            meta.last_used = now
            if mode and session_id:
                meta.last_session = LastSessionInfo(mode=mode, session_id=session_id)
            projects[existing_idx] = meta.to_dict()
        else:
            last_session = None
            if mode and session_id:
                last_session = LastSessionInfo(mode=mode, session_id=session_id)
            meta = ProjectMetadata(
                path=path_str,
                id=project_id,
                name=project_name,
                last_session=last_session,
                last_used=now,
                created_at=now,
            )
            projects.append(meta.to_dict())

        self._data["projects"] = projects
        self._save()

    def list_recent_projects(self, limit: int = 10) -> List[ProjectMetadata]:
        projects = [ProjectMetadata.from_dict(p) for p in self._data.get("projects", [])]
        projects.sort(key=lambda x: x.last_used, reverse=True)
        return projects[:limit]

    def remove_project(self, project_path: Path) -> bool:
        path_str = str(project_path.resolve())
        projects = self._data.get("projects", [])
        original_len = len(projects)
        self._data["projects"] = [p for p in projects if p.get("path") != path_str]
        if len(self._data["projects"]) < original_len:
            self._save()
            return True
        return False
