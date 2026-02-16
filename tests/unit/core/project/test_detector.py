import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.project.detector import detect_project_root, is_iris_source_project


class TestDetectProjectRoot:
    def test_detect_git_project(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_detect_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").touch()
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_detect_iris_marker(self, tmp_path: Path):
        (tmp_path / ".iris").mkdir()
        subdir = tmp_path / "app"
        subdir.mkdir()

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_no_project_marker(self, tmp_path: Path):
        subdir = tmp_path / "random" / "dir"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)
        assert result is None

    def test_detect_from_cwd(self, tmp_path: Path):
        (tmp_path / ".git").mkdir()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = detect_project_root()
            assert result == tmp_path

    def test_marker_priority_prefers_nearest(self, tmp_path: Path):
        (tmp_path / ".iris").mkdir()
        inner_dir = tmp_path / "inner"
        inner_dir.mkdir()
        (inner_dir / ".git").mkdir()

        result = detect_project_root(inner_dir)
        assert result == inner_dir


class TestIsIrisSourceProject:
    def test_is_iris_source(self, tmp_path: Path):
        (tmp_path / "src" / "core" / "project").mkdir(parents=True)
        (tmp_path / "src" / "application" / "cli").mkdir(parents=True)

        assert is_iris_source_project(tmp_path) is True

    def test_not_iris_source(self, tmp_path: Path):
        (tmp_path / "src" / "app").mkdir(parents=True)

        assert is_iris_source_project(tmp_path) is False
