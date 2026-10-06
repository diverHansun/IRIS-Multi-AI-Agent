"""Exercise the actual POSIX process used by macOS DeepAgent shell tools."""

import os

import pytest

from src.components.deepagents.runtime_middlewares.shell import ShellConfig
from src.components.deepagents.runtime_middlewares.shell.session import PersistentShellSession


@pytest.mark.skipif(os.name == 'nt', reason='Real POSIX shell process')
def test_real_shell_preserves_state_and_utf8_in_workspace_with_spaces(tmp_path):
    workspace = tmp_path / '中文 workspace'
    workspace.mkdir()
    config = ShellConfig(shell_type='auto', workspace_root=workspace)
    session = PersistentShellSession(
        workspace=config.workspace_root,
        shell_command=config.get_shell_command(),
        environment={'LANG': 'en_US.UTF-8'},
        command_timeout=5,
        startup_timeout=5,
        max_output_lines=100,
        max_output_bytes=1048576,
    )
    try:
        session.start()
        result = session.execute("export IRIS_MAC_TEST='你好 Mac'; printf '%s\\n' \"$IRIS_MAC_TEST\"")
        assert result.exit_code == 0
        assert '你好 Mac' in result.output
        result = session.execute("printf '%s\\n' \"$IRIS_MAC_TEST\"; pwd")
        assert result.exit_code == 0
        assert '你好 Mac' in result.output
        assert str(workspace.resolve()) in result.output
        assert session.execute('false').exit_code == 1
    finally:
        session.stop()
    assert not session.is_alive()
