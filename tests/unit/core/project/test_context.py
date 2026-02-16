import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.project.context import ProjectContext


class TestProjectContext:
    def test_from_path_with_git(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()

        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.project_path == tmp_path
        assert ctx.project_name == tmp_path.name
        assert ctx.is_iris_source is False
        assert tmp_path.name in ctx.project_id
        assert len(ctx.project_id.split("_")[-1]) == 8

    def test_from_cwd(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            ctx = ProjectContext.from_cwd()
            assert ctx.project_path == tmp_path

    def test_iris_dir_property(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.iris_dir == tmp_path / ".iris"

    def test_config_file_property(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.config_file == tmp_path / ".iris" / "config.json"

    def test_skills_dir_property(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.skills_dir == tmp_path / ".iris" / "skills"

    def test_get_storage_dir(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.get_storage_dir("llm") == tmp_path / ".iris" / "sessions" / "llm"
        assert ctx.get_storage_dir("basic") == tmp_path / ".iris" / "sessions" / "basicagent"
        assert ctx.get_storage_dir("deep") == tmp_path / ".iris" / "sessions" / "deepagent"

    def test_ensure_structure(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        ctx.ensure_structure()

        assert (tmp_path / ".iris" / "sessions" / "llm").exists()
        assert (tmp_path / ".iris" / "sessions" / "basicagent").exists()
        assert (tmp_path / ".iris" / "sessions" / "deepagent").exists()
        assert not (tmp_path / ".iris" / "skills").exists()

    def test_get_storage_dirs_dict(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        dirs = ctx.get_storage_dirs_dict()

        assert "llm" in dirs
        assert "basic" in dirs
        assert "deep" in dirs

    def test_project_id_generation(self, tmp_path: Path):
        project_dir = tmp_path / "my-test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)

        assert ctx.project_id.startswith("my-test-project_")
        assert len(ctx.project_id.split("_")[-1]) == 8

    def test_project_id_with_special_chars(self, tmp_path: Path):
        project_dir = tmp_path / "my project @2024!"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)

        assert "@" not in ctx.project_id
        assert "!" not in ctx.project_id
        assert " " not in ctx.project_id

    def test_fallback_to_current_dir(self, tmp_path: Path):
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.project_path == tmp_path.resolve()
