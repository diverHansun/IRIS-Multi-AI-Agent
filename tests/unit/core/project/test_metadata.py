import json
from pathlib import Path

from src.core.project.metadata import (
    ProjectMetadata,
    LastSessionInfo,
    MetadataManager,
)


class TestProjectMetadata:
    def test_to_dict(self):
        meta = ProjectMetadata(
            path="/test/path",
            id="test_12345678",
            name="test",
            last_session=LastSessionInfo(mode="deep", session_id="session_1"),
        )

        data = meta.to_dict()

        assert data["path"] == "/test/path"
        assert data["id"] == "test_12345678"
        assert data["last_session"]["mode"] == "deep"

    def test_from_dict(self):
        data = {
            "path": "/test/path",
            "id": "test_12345678",
            "name": "test",
            "last_session": {"mode": "llm", "session_id": "s1"},
            "last_used": "2025-01-20T10:00:00",
            "created_at": "2025-01-15T09:00:00",
        }

        meta = ProjectMetadata.from_dict(data)

        assert meta.path == "/test/path"
        assert meta.last_session.mode == "llm"

    def test_from_dict_without_last_session(self):
        data = {
            "path": "/test/path",
            "id": "test_12345678",
            "name": "test",
        }

        meta = ProjectMetadata.from_dict(data)

        assert meta.last_session is None


class TestMetadataManager:
    def test_init_creates_empty_structure(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        assert manager._data["version"] == "1.0"
        assert manager._data["projects"] == []

    def test_load_existing_file(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        existing_data = {
            "version": "1.0",
            "projects": [
                {"path": "/test", "id": "test_1", "name": "test"}
            ]
        }
        metadata_file.write_text(json.dumps(existing_data))

        manager = MetadataManager(metadata_file)

        assert len(manager._data["projects"]) == 1

    def test_get_project_exists(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "my-project"
        manager.update_project(project_path, "my-project_abc", "my-project")

        meta = manager.get_project(project_path)

        assert meta is not None
        assert meta.name == "my-project"

    def test_get_project_not_exists(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        meta = manager.get_project(tmp_path / "nonexistent")

        assert meta is None

    def test_update_project_new(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "new-project"
        manager.update_project(
            project_path,
            "new-project_abc",
            "new-project",
            mode="basic",
            session_id="session_1"
        )

        meta = manager.get_project(project_path)
        assert meta is not None
        assert meta.last_session.mode == "basic"
        assert meta.last_session.session_id == "session_1"

    def test_update_project_existing(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "project"

        manager.update_project(project_path, "project_abc", "project", mode="llm", session_id="s1")
        manager.update_project(project_path, "project_abc", "project", mode="deep", session_id="s2")

        meta = manager.get_project(project_path)
        assert meta.last_session.mode == "deep"
        assert meta.last_session.session_id == "s2"

    def test_list_recent_projects(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        for i in range(5):
            project_path = tmp_path / f"project-{i}"
            manager.update_project(project_path, f"project-{i}_abc", f"project-{i}")

        projects = manager.list_recent_projects(limit=3)

        assert len(projects) == 3

    def test_remove_project(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "to-remove"
        manager.update_project(project_path, "to-remove_abc", "to-remove")

        result = manager.remove_project(project_path)

        assert result is True
        assert manager.get_project(project_path) is None

    def test_save_and_reload(self, tmp_path: Path):
        metadata_file = tmp_path / "metadata.json"

        manager1 = MetadataManager(metadata_file)
        project_path = tmp_path / "persistent"
        manager1.update_project(project_path, "persistent_abc", "persistent")

        manager2 = MetadataManager(metadata_file)
        meta = manager2.get_project(project_path)

        assert meta is not None
        assert meta.name == "persistent"
