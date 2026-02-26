"""Unit tests for shell middleware."""

import ast
import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage

from src.components.deepagents.runtime_middlewares.shell import (
    SecurityPolicyConfig,
    ShellConfig,
    ShellToolMiddleware,
    build_shell_config,
)


class TestShellConfig:
    """Test shell configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ShellConfig()

        assert config.enabled is True
        assert config.workspace_root == Path.cwd()
        assert config.command_timeout == 30.0
        assert config.startup_timeout == 10.0
        assert config.termination_timeout == 5.0
        assert config.max_output_lines == 100
        assert config.max_output_bytes == 1048576
        assert config.environment == {}
        assert config.startup_commands == []
        assert config.security_policy.enabled is False

    def test_custom_config(self):
        """Test custom configuration values."""
        workspace = Path(tempfile.gettempdir())
        config = ShellConfig(
            enabled=False,
            workspace_root=workspace,
            shell_type="powershell",
            command_timeout=60.0,
            startup_timeout=20.0,
            termination_timeout=10.0,
            max_output_lines=200,
            max_output_bytes=2097152,
            environment={"TEST": "value"},
            startup_commands=["cd /tmp"],
            security_policy=SecurityPolicyConfig(enabled=True),
        )

        assert config.enabled is False
        assert config.workspace_root == workspace
        assert config.shell_type == "powershell"
        assert config.command_timeout == 60.0
        assert config.startup_timeout == 20.0
        assert config.termination_timeout == 10.0
        assert config.max_output_lines == 200
        assert config.max_output_bytes == 2097152
        assert config.environment == {"TEST": "value"}
        assert config.startup_commands == ["cd /tmp"]
        assert config.security_policy.enabled is True

    def test_validation_errors(self):
        """Test configuration validation."""
        with pytest.raises(ValueError, match="command_timeout must be positive"):
            ShellConfig(command_timeout=0)

        with pytest.raises(ValueError, match="startup_timeout must be positive"):
            ShellConfig(startup_timeout=-1)

        with pytest.raises(ValueError, match="max_output_lines must be positive"):
            ShellConfig(max_output_lines=0)

    def test_get_shell_command_windows(self):
        """Test shell command for Windows."""
        if os.name != "nt":
            pytest.skip("Windows only test")

        config_cmd = ShellConfig(shell_type="cmd")
        assert config_cmd.get_shell_command() == ["cmd.exe", "/Q"]

        config_ps = ShellConfig(shell_type="powershell")
        assert config_ps.get_shell_command() == ["powershell.exe", "-NoLogo", "-NoProfile"]

    def test_get_shell_command_unix(self):
        """Test shell command for Unix."""
        if os.name == "nt":
            pytest.skip("Unix only test")

        config = ShellConfig(shell_type="bash")
        assert config.get_shell_command() == ["/bin/bash", "--norc", "--noprofile"]

    def test_build_shell_config(self):
        """Test building config from dictionary."""
        config_dict = {
            "enabled": True,
            "workspace_root": ".",
            "shell_type": "cmd",
            "command_timeout": 45.0,
            "max_output_lines": 150,
            "environment": {"KEY": "value"},
            "startup_commands": ["echo test"],
            "security_policy": {"enabled": True},
        }

        config = build_shell_config(config_dict)

        assert config.enabled is True
        assert config.shell_type == "cmd"
        assert config.command_timeout == 45.0
        assert config.max_output_lines == 150
        assert config.environment == {"KEY": "value"}
        assert config.startup_commands == ["echo test"]
        assert config.security_policy.enabled is True

    def test_build_shell_config_auto_uses_project_root(self, tmp_path: Path):
        """'auto' should resolve to the provided project root."""
        config = build_shell_config({"workspace_root": "auto"}, project_root=tmp_path)
        assert config.workspace_root == tmp_path.resolve()

    def test_build_shell_config_relative_path_uses_project_root(self, tmp_path: Path):
        """Relative paths should resolve from project_root when provided."""
        config = build_shell_config(
            {"workspace_root": "subdir/work"},
            project_root=tmp_path,
        )
        assert config.workspace_root == (tmp_path / "subdir" / "work").resolve()

    def test_build_shell_config_dot_uses_project_root(self, tmp_path: Path):
        """'.' should follow project_root in the defensive component layer."""
        config = build_shell_config({"workspace_root": "."}, project_root=tmp_path)
        assert config.workspace_root == tmp_path.resolve()

    def test_build_shell_config_relative_path_without_project_root_uses_cwd(self):
        """Relative paths should fall back to current process cwd without project_root."""
        config = build_shell_config({"workspace_root": "subdir/work"})
        assert config.workspace_root == Path("subdir/work").resolve()

    def test_build_shell_config_accepts_string_project_root(self, tmp_path: Path):
        """project_root may be provided as a string and should be normalized."""
        config = build_shell_config({"workspace_root": "auto"}, project_root=str(tmp_path))
        assert config.workspace_root == tmp_path.resolve()


class TestShellToolMiddleware:
    """Test shell tool middleware."""

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        config = ShellConfig(workspace_root=Path.cwd())
        middleware = ShellToolMiddleware(config=config)

        assert middleware.config == config
        assert len(middleware.tools) == 1
        assert middleware.tools[0].name == "shell"

    def test_middleware_get_tools(self):
        """Test get_tools method."""
        config = ShellConfig(workspace_root=Path.cwd())
        middleware = ShellToolMiddleware(config=config)

        tools = middleware.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "shell"

    def test_middleware_describe(self):
        """Test describe method."""
        config = ShellConfig(
            enabled=True,
            workspace_root=Path.cwd(),
            shell_type="cmd",
            command_timeout=30.0,
            max_output_lines=100,
            max_output_bytes=1048576,
            security_policy=SecurityPolicyConfig(enabled=True),
        )
        middleware = ShellToolMiddleware(config=config)

        description = middleware.describe()

        assert description["enabled"] is True
        assert description["shell_type"] == "cmd"
        assert description["command_timeout"] == 30.0
        assert description["max_output_lines"] == 100
        assert description["max_output_bytes"] == 1048576
        assert description["security_policy_enabled"] is True
        assert description["tools"] == ["shell"]

    def test_custom_tool_description(self):
        """Test custom tool description."""
        config = ShellConfig(workspace_root=Path.cwd())
        custom_desc = "Custom shell tool description"
        middleware = ShellToolMiddleware(config=config, tool_description=custom_desc)

        assert middleware.tools[0].description == custom_desc

    def test_awrap_tool_call_awaits_non_shell_handler(self):
        """Ensure awrap_tool_call awaits the provided handler for non-shell tools."""
        async def run_test():
            config = ShellConfig(workspace_root=Path.cwd())
            middleware = ShellToolMiddleware(config=config)
            request = ToolCallRequest(
                tool_call={"name": "dummy", "args": {}, "id": "call-1"},
                tool=None,
                state={},
                runtime=None,
            )

            handler_called = False

            async def handler(_: ToolCallRequest) -> ToolMessage:
                nonlocal handler_called
                handler_called = True
                return ToolMessage(content="ok", tool_call_id="call-1", name="dummy")

            result = await middleware.awrap_tool_call(request, handler)

            assert handler_called is True
            assert isinstance(result, ToolMessage)
            assert result.content == "ok"

        asyncio.run(run_test())

    def test_awrap_tool_call_handles_shell_without_handler(self):
        """Ensure awrap_tool_call executes shell tools without invoking handler."""
        async def run_test():
            config = ShellConfig(workspace_root=Path.cwd())
            middleware = ShellToolMiddleware(config=config)
            shell_tool = middleware.tools[0]

            # Prevent spawning a real shell session during the test.
            middleware._get_or_create_session = lambda state: object()  # type: ignore[assignment]
            middleware._execute_command = (
                lambda session, command, timeout: {"status": "success", "command": command}
            )

            request = ToolCallRequest(
                tool_call={"name": "shell", "args": {"command": "echo hi"}, "id": "call-2"},
                tool=shell_tool,
                state={},
                runtime=None,
            )

            async def handler(_: ToolCallRequest):
                raise AssertionError("Handler should not be invoked for shell calls.")

            result = await middleware.awrap_tool_call(request, handler)

            assert isinstance(result, ToolMessage)
            assert result.tool_call_id == "call-2"
            payload = ast.literal_eval(result.content)
            assert payload["status"] == "success"

        asyncio.run(run_test())

    def test_execute_command_passes_timeout_override_on_success(self):
        """timeout_override should be passed into session.execute without private mutation."""
        config = ShellConfig(workspace_root=Path.cwd(), command_timeout=30.0)
        middleware = ShellToolMiddleware(config=config)

        class FakeSession:
            def __init__(self):
                self._command_timeout = 30.0

            def execute(self, command: str, *, timeout_override=None, **kwargs):
                assert command == "echo ok"
                assert timeout_override == 5.0
                assert self._command_timeout == 30.0
                return type(
                    "Result",
                    (),
                    {
                        "exit_code": 0,
                        "timed_out": False,
                        "truncated_by_lines": False,
                        "truncated_by_bytes": False,
                        "duration": 0.1234,
                        "output": "ok",
                    },
                )()

        session = FakeSession()
        result = middleware._execute_command(session, "echo ok", timeout_override=5.0)

        assert session._command_timeout == 30.0
        assert result["status"] == "success"
        assert result["duration"] == 0.123

    def test_execute_command_passes_timeout_override_on_exception(self):
        """timeout_override should be passed even when execution raises."""
        config = ShellConfig(workspace_root=Path.cwd(), command_timeout=30.0)
        middleware = ShellToolMiddleware(config=config)

        class FakeSession:
            def __init__(self):
                self._command_timeout = 30.0

            def execute(self, command: str, *, timeout_override=None, **kwargs):
                assert command == "boom"
                assert timeout_override == 5.0
                assert self._command_timeout == 30.0
                raise RuntimeError("kaboom")

        session = FakeSession()
        result = middleware._execute_command(session, "boom", timeout_override=5.0)

        assert session._command_timeout == 30.0
        assert result["status"] == "error"
        assert "kaboom" in result["error"]

    def test_execute_command_ignores_non_positive_timeout_override(self):
        """Non-positive timeout overrides should not be forwarded to the session."""
        config = ShellConfig(workspace_root=Path.cwd(), command_timeout=30.0)
        middleware = ShellToolMiddleware(config=config)

        class FakeSession:
            def __init__(self):
                self._command_timeout = 30.0

            def execute(self, command: str, *, timeout_override=None, **kwargs):
                assert command == "echo ok"
                assert timeout_override is None
                return type(
                    "Result",
                    (),
                    {
                        "exit_code": 0,
                        "timed_out": False,
                        "truncated_by_lines": False,
                        "truncated_by_bytes": False,
                        "duration": 0.01,
                        "output": "ok",
                    },
                )()

        result_zero = middleware._execute_command(FakeSession(), "echo ok", timeout_override=0)
        result_negative = middleware._execute_command(FakeSession(), "echo ok", timeout_override=-1)

        assert result_zero["status"] == "success"
        assert result_negative["status"] == "success"

    def test_execute_command_returns_blocked_status(self):
        """Policy-blocked commands should be surfaced as status=blocked."""
        config = ShellConfig(workspace_root=Path.cwd(), command_timeout=30.0)
        middleware = ShellToolMiddleware(config=config)

        class FakeSession:
            def __init__(self):
                self._command_timeout = 30.0

            def execute(self, command: str, *, timeout_override=None, **kwargs):
                assert command == "rm -rf /"
                assert timeout_override is None
                return type(
                    "Result",
                    (),
                    {
                        "exit_code": None,
                        "timed_out": False,
                        "truncated_by_lines": False,
                        "truncated_by_bytes": False,
                        "duration": 0.001,
                        "output": "Command 'rm' is blocked by security policy.",
                        "blocked": True,
                    },
                )()

        result = middleware._execute_command(FakeSession(), "rm -rf /", timeout_override=None)

        assert result["status"] == "blocked"
        assert result["blocked"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
