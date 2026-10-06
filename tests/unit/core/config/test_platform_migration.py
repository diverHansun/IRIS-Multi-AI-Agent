"""Configuration migration and first-install behavior on a new host."""

from src.core.config.initializer import ConfigInitializer
from src.core.config.paths import resolve_config_path


def test_windows_config_reference_resolves_on_posix(tmp_path):
    target = tmp_path / 'llm' / 'providers.json'
    target.parent.mkdir()
    target.write_text('{}')
    assert resolve_config_path(r'config\llm\providers.json', user_dir=tmp_path) == target


def test_first_install_copies_filesystem_templates_and_preserves_edits(tmp_path):
    initializer = ConfigInitializer(share_dir=tmp_path)
    assert initializer.initialize(quiet=True)
    directory = tmp_path / 'agents' / 'deep' / 'middleware' / 'filesystem'
    real_config = directory / 'real_filesystem.json'
    assert real_config.exists()
    assert (directory / 'virtual_filesystem.json').exists()
    real_config.write_text('{"enabled": false}')
    initializer.initialize(quiet=True)
    assert real_config.read_text() == '{"enabled": false}'


def test_initialization_prefers_repository_config_over_example(tmp_path):
    bundled = tmp_path / 'bundled'
    templates = bundled / 'agents/deep/middleware/filesystem'
    templates.mkdir(parents=True)
    (templates / 'real_filesystem.json').write_text('{"enabled": false}')
    (templates / 'real_files.example.json').write_text('{"enabled": true}')
    target = tmp_path / 'user'
    initializer = ConfigInitializer(share_dir=target)
    initializer._config_dir = bundled
    assert initializer.initialize(quiet=True)
    assert (target / 'agents/deep/middleware/filesystem/real_filesystem.json').read_text() == '{"enabled": false}'
