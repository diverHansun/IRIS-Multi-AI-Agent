from pathlib import Path
from unittest.mock import patch

from src.core.project.share import IrisShareDir


class TestIrisShareDir:
    def test_get_share_dir_creates_directory(self, tmp_path: Path):
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            share_dir = IrisShareDir.get_share_dir()

            assert share_dir.exists()
            assert share_dir == home_dir / ".iris"

    def test_get_metadata_file(self, tmp_path: Path):
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            metadata_file = IrisShareDir.get_metadata_file()

            assert metadata_file == home_dir / ".iris" / "metadata.json"

    def test_get_global_config_file(self, tmp_path: Path):
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            config_file = IrisShareDir.get_global_config_file()

            assert config_file == home_dir / ".iris" / "config.json"

    def test_get_skills_dir(self, tmp_path: Path):
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            skills_dir = IrisShareDir.get_skills_dir()

            assert skills_dir.exists()
            assert skills_dir == home_dir / ".iris" / "skills"
