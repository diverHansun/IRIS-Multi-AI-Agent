import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.config.loader import ConfigLoader


class TestConfigLoaderDeepPathFallbacks(unittest.TestCase):
    """Regression tests for canonical deep config paths and legacy fallbacks."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user_dir = self.temp_dir / "user"
        self.project_dir = self.temp_dir / "project"
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_prefers_canonical_root_over_legacy_models_in_same_scope(self) -> None:
        self._write_json(
            self.user_dir / "agents" / "deep" / "mainagents.json",
            {"source": "root"},
        )
        self._write_json(
            self.user_dir / "agents" / "deep" / "models" / "mainagents.json",
            {"source": "legacy"},
        )

        loader = ConfigLoader(user_config_dir=self.user_dir)
        data = loader.load_json_config("agents/deep/mainagents.json", merge_project=False)

        assert data == {"source": "root"}

    def test_uses_legacy_models_when_canonical_root_is_missing(self) -> None:
        self._write_json(
            self.user_dir / "agents" / "deep" / "models" / "subagents.json",
            {"source": "legacy"},
        )

        loader = ConfigLoader(user_config_dir=self.user_dir)
        data = loader.load_json_config("agents/deep/subagents.json", merge_project=False)

        assert data == {"source": "legacy"}

    def test_project_canonical_overrides_user_legacy_config(self) -> None:
        self._write_json(
            self.user_dir / "agents" / "deep" / "models" / "mainagents.json",
            {"user_value": 1, "shared": {"scope": "user"}},
        )
        self._write_json(
            self.project_dir / "agents" / "deep" / "mainagents.json",
            {"project_value": 2, "shared": {"scope": "project"}},
        )

        loader = ConfigLoader(
            user_config_dir=self.user_dir,
            project_config_dir=self.project_dir,
        )
        data = loader.load_json_config("agents/deep/mainagents.json", merge_project=True)

        assert data == {
            "user_value": 1,
            "project_value": 2,
            "shared": {"scope": "project"},
        }

    def test_load_shared_json_supports_bundled_legacy_models_fallback(self) -> None:
        bundled_config_dir = self.temp_dir / "bundled-config"
        self._write_json(
            bundled_config_dir / "agents" / "deep" / "models" / "subagents.json",
            {"source": "bundled-legacy"},
        )

        loader = ConfigLoader(user_config_dir=self.user_dir)
        with patch("src.core.config.loader.find_config_dir", return_value=bundled_config_dir):
            data = loader.load_shared_json("agents/deep/subagents.json", merge_project=False)

        assert data == {"source": "bundled-legacy"}
