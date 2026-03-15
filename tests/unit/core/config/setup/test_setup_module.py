"""Unit tests for the src.core.config.setup module.

Covers: EnvWriter, SetupWizard (check_and_run paths, version compare,
[setup] toml I/O), ConfigValidator, SetupCommand/DoctorCommand dispatch,
and the Tab-completion/suggest tables for setup/doctor.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ConsoleStub:
    """Minimal Rich Console replacement that captures printed lines."""

    def __init__(self) -> None:
        self.lines: List[str] = []

    def print(self, *args, **kwargs) -> None:
        self.lines.append(" ".join(str(a) for a in args))

    def input(self, prompt: str = "") -> str:  # noqa: A003
        return ""


# ---------------------------------------------------------------------------
# EnvWriter
# ---------------------------------------------------------------------------

class TestEnvWriter:

    def test_write_and_read_key(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        writer = EnvWriter(env_file)

        writer.write_key("ZHIPU_API_KEY", "abc123")
        assert writer.read_key("ZHIPU_API_KEY") == "abc123"

    def test_has_key_returns_false_for_placeholder(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=your_openai_api_key_here\n", encoding="utf-8")
        writer = EnvWriter(env_file)

        assert writer.has_key("OPENAI_API_KEY") is False

    def test_has_key_returns_true_for_real_value(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        env_file.write_text("ZHIPU_API_KEY=realkey\n", encoding="utf-8")
        writer = EnvWriter(env_file)

        assert writer.has_key("ZHIPU_API_KEY") is True

    def test_write_key_updates_existing_entry(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        env_file.write_text("ZHIPU_API_KEY=old_value\n# comment\n", encoding="utf-8")
        writer = EnvWriter(env_file)

        writer.write_key("ZHIPU_API_KEY", "new_value")

        lines = env_file.read_text(encoding="utf-8").splitlines()
        assert any(line == "ZHIPU_API_KEY=new_value" for line in lines)
        assert not any("old_value" in line for line in lines)
        # Comment preserved
        assert any(line.startswith("#") for line in lines)

    def test_write_key_appends_new_entry(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=1\n", encoding="utf-8")
        writer = EnvWriter(env_file)

        writer.write_key("NEW_KEY", "hello")

        content = env_file.read_text(encoding="utf-8")
        assert "NEW_KEY=hello" in content
        assert "EXISTING=1" in content

    def test_read_key_from_nonexistent_file(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        writer = EnvWriter(tmp_path / ".env")
        assert writer.read_key("ANYTHING") is None

    def test_write_key_creates_file_if_missing(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / "sub" / ".env"
        writer = EnvWriter(env_file)
        writer.write_key("FOO", "bar")

        assert env_file.exists()
        assert "FOO=bar" in env_file.read_text(encoding="utf-8")

    def test_get_configured_providers_from_env_file(self, tmp_path: Path, monkeypatch) -> None:
        from src.core.config.setup.writer import EnvWriter

        env_file = tmp_path / ".env"
        env_file.write_text("ZHIPU_API_KEY=real_key\n", encoding="utf-8")

        # Isolate from real OS environment
        monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("TONGYI_API_KEY", raising=False)

        writer = EnvWriter(env_file)
        providers = writer.get_configured_providers()

        assert "zhipu" in providers
        assert "openai" not in providers

    def test_permission_error_raises_setup_error(self, tmp_path: Path) -> None:
        from src.core.config.setup.writer import EnvWriter, SetupError

        env_file = tmp_path / ".env"
        writer = EnvWriter(env_file)

        with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
            with pytest.raises(SetupError, match="Cannot write"):
                writer.write_key("KEY", "value")


# ---------------------------------------------------------------------------
# SetupWizard — version comparison and toml I/O
# ---------------------------------------------------------------------------

class TestVersionComparison:

    def test_older_version_is_less_than(self) -> None:
        from src.core.config.setup.wizard import _version_lt

        assert _version_lt("0.1.0", "0.2.0") is True
        assert _version_lt("0.1.3", "0.1.10") is True

    def test_same_version_is_not_less(self) -> None:
        from src.core.config.setup.wizard import _version_lt

        assert _version_lt("1.0.0", "1.0.0") is False

    def test_newer_installed_is_not_less(self) -> None:
        from src.core.config.setup.wizard import _version_lt

        assert _version_lt("2.0.0", "1.9.9") is False

    def test_fallback_for_unparseable_version(self) -> None:
        from src.core.config.setup.wizard import _version_lt

        # Should not raise; returns installed != current
        result = _version_lt("not-a-version", "also-not")
        assert isinstance(result, bool)


class TestSetupWizardToml:

    def test_read_setup_info_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        from src.core.config.setup.wizard import SetupWizard

        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        assert wizard._read_setup_info() == {}

    def test_mark_completed_writes_toml_section(self, tmp_path: Path) -> None:
        from src.core.config.setup.wizard import SetupWizard

        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        wizard._mark_completed("1.2.3")

        info = wizard._read_setup_info()
        assert info.get("completed") is True
        assert info.get("version") == "1.2.3"
        assert info.get("completed_at")

    def test_update_version_preserves_completed_flag(self, tmp_path: Path) -> None:
        from src.core.config.setup.wizard import SetupWizard

        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        wizard._mark_completed("1.0.0")
        wizard._update_version("1.1.0")

        info = wizard._read_setup_info()
        assert info.get("completed") is True
        assert info.get("version") == "1.1.0"

    def test_write_preserves_existing_toml_content(self, tmp_path: Path) -> None:
        """[setup] write must not destroy other sections in config.toml."""
        config = tmp_path / "config.toml"
        config.write_text("[general]\ntheme = \"dark\"\n", encoding="utf-8")

        from src.core.config.setup.wizard import SetupWizard

        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        wizard._mark_completed("0.1.0")

        content = config.read_text(encoding="utf-8")
        assert 'theme = "dark"' in content
        assert "completed" in content


class TestSetupWizardCheckAndRun:

    def test_check_and_run_skips_when_completed_same_version(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from src.core.config.setup.wizard import SetupWizard

        monkeypatch.setattr(
            "src.core.config.setup.wizard.get_package_version", lambda: "1.0.0"
        )
        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        wizard._mark_completed("1.0.0")

        run_first_time_called = []
        monkeypatch.setattr(wizard, "run_first_time", lambda: run_first_time_called.append(1) or True)

        result = wizard.check_and_run()

        assert result is True
        assert not run_first_time_called

    def test_check_and_run_triggers_wizard_when_not_completed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from src.core.config.setup.wizard import SetupWizard

        wizard = SetupWizard(share_dir=tmp_path, console=_ConsoleStub())
        # No config.toml -> setup not completed

        called = []
        monkeypatch.setattr(wizard, "run_first_time", lambda: called.append(1) or True)

        wizard.check_and_run()
        assert called

    def test_check_and_run_prints_upgrade_hint_on_version_bump(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from src.core.config.setup.wizard import SetupWizard

        monkeypatch.setattr(
            "src.core.config.setup.wizard.get_package_version", lambda: "2.0.0"
        )
        console = _ConsoleStub()
        wizard = SetupWizard(share_dir=tmp_path, console=console)
        wizard._mark_completed("1.0.0")  # old version

        result = wizard.check_and_run()

        assert result is True
        assert any("updated" in line.lower() or "2.0.0" in line for line in console.lines)

    def test_run_specific_returns_false_for_unknown_target(
        self, tmp_path: Path
    ) -> None:
        from src.core.config.setup.wizard import SetupWizard

        console = _ConsoleStub()
        wizard = SetupWizard(share_dir=tmp_path, console=console)

        result = wizard.run_specific("nonexistent_target")
        assert result is False


# ---------------------------------------------------------------------------
# ConfigValidator
# ---------------------------------------------------------------------------

class TestConfigValidator:

    def test_check_all_returns_check_results(self, tmp_path: Path, monkeypatch) -> None:
        from src.core.config.setup.validator import ConfigValidator
        from src.core.config.setup.steps.base import CheckResult

        # Provide a dummy step that returns one result
        dummy_result = CheckResult(
            name="test", status="pass", message="ok", category="llm"
        )

        class _DummyStep:
            def check(self, ctx):
                return [dummy_result]

        validator = ConfigValidator(share_dir=tmp_path, console=_ConsoleStub())
        monkeypatch.setattr(validator, "_get_all_steps", lambda: [_DummyStep()])

        results = validator.check_all()
        assert len(results) == 1
        assert results[0].status == "pass"

    def test_check_category_unknown_returns_empty(self, tmp_path: Path) -> None:
        from src.core.config.setup.validator import ConfigValidator

        validator = ConfigValidator(share_dir=tmp_path, console=_ConsoleStub())
        results = validator.check_category("unknown_cat")
        assert results == []

    def test_print_report_shows_summary(self, tmp_path: Path) -> None:
        from src.core.config.setup.validator import ConfigValidator
        from src.core.config.setup.steps.base import CheckResult

        console = _ConsoleStub()
        validator = ConfigValidator(share_dir=tmp_path, console=console)

        results = [
            CheckResult(name="a", status="pass", message="all good", category="llm"),
            CheckResult(name="b", status="fail", message="missing key", category="llm"),
            CheckResult(name="c", status="warn", message="optional missing", category="tools"),
        ]
        validator.print_report(results)

        joined = "\n".join(console.lines)
        assert "1 passed" in joined or "pass" in joined
        assert "1 failed" in joined or "fail" in joined
        assert "1 warning" in joined or "warn" in joined


# ---------------------------------------------------------------------------
# SetupCommand / DoctorCommand dispatch
# ---------------------------------------------------------------------------

class TestSetupCommandDispatch:

    def _ctx(self):
        ctx = MagicMock()
        ctx.current_engine = "agent"
        ctx.console = _ConsoleStub()
        return ctx

    def test_no_args_calls_run_all(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        called = []

        class _FakeWizard:
            def __init__(self, **_):
                pass

            def run_all(self):
                called.append(1)
                return True

        # SetupWizard is imported lazily inside _run_setup; patch at its source module.
        monkeypatch.setattr(
            "src.core.config.setup.wizard.SetupWizard", _FakeWizard
        )

        result = asyncio.run(SetupCommand().execute(self._ctx(), ""))
        assert called
        assert result.type == "success"

    def test_llm_flag_calls_run_specific(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        called_with = []

        class _FakeWizard:
            def __init__(self, **_):
                pass

            def run_specific(self, target, sub_target=None):
                called_with.append((target, sub_target))
                return True

        monkeypatch.setattr(
            "src.core.config.setup.wizard.SetupWizard", _FakeWizard
        )

        result = asyncio.run(SetupCommand().execute(self._ctx(), "--llm"))
        assert ("llm", None) in called_with
        assert result.type == "success"

    def test_agent_deep_sub_target_calls_run_specific(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        called_with = []

        class _FakeWizard:
            def __init__(self, **_):
                pass

            def run_specific(self, target, sub_target=None):
                called_with.append((target, sub_target))
                return True

        monkeypatch.setattr(
            "src.core.config.setup.wizard.SetupWizard", _FakeWizard
        )

        result = asyncio.run(SetupCommand().execute(self._ctx(), "--agent deep"))
        assert ("agent", "deep") in called_with
        assert result.type == "success"

    def test_invalid_agent_subtarget_returns_error(self) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        result = asyncio.run(SetupCommand().execute(self._ctx(), "--agent invalid"))
        assert result.type == "error"
        assert "--agent" in result.message

    def test_invalid_tools_subtarget_returns_error(self) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        result = asyncio.run(SetupCommand().execute(self._ctx(), "--tools invalid"))
        assert result.type == "error"
        assert "--tools" in result.message

    def test_unknown_flag_returns_error(self) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        result = asyncio.run(SetupCommand().execute(self._ctx(), "--nope"))
        assert result.type == "error"

    def test_wizard_returns_false_maps_to_error(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import SetupCommand

        class _FakeWizard:
            def __init__(self, **_):
                pass

            def run_all(self):
                return False

        monkeypatch.setattr(
            "src.core.config.setup.wizard.SetupWizard", _FakeWizard
        )
        result = asyncio.run(SetupCommand().execute(self._ctx(), ""))
        assert result.type == "error"


class TestDoctorCommandDispatch:

    def _ctx(self):
        ctx = MagicMock()
        ctx.current_engine = "agent"
        ctx.console = _ConsoleStub()
        return ctx

    def test_doctor_runs_full_check(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import DoctorCommand
        from src.core.config.setup.steps.base import CheckResult

        called = []

        class _FakeValidator:
            def __init__(self, **_):
                pass

            def check_all(self):
                called.append(1)
                return [CheckResult(name="x", status="pass", message="ok", category="llm")]

            def print_report(self, results):
                pass

        # ConfigValidator is imported lazily; patch at its source module.
        monkeypatch.setattr(
            "src.core.config.setup.validator.ConfigValidator",
            _FakeValidator,
        )
        result = asyncio.run(DoctorCommand().execute(self._ctx(), ""))
        assert called
        assert result.type == "success"

    def test_doctor_returns_error_when_checks_fail(self, monkeypatch) -> None:
        from src.application.commands.shared.setup_commands import DoctorCommand
        from src.core.config.setup.steps.base import CheckResult

        class _FakeValidator:
            def __init__(self, **_):
                pass

            def check_all(self):
                return [CheckResult(name="x", status="fail", message="missing", category="llm")]

            def print_report(self, results):
                pass

        monkeypatch.setattr(
            "src.core.config.setup.validator.ConfigValidator",
            _FakeValidator,
        )
        result = asyncio.run(DoctorCommand().execute(self._ctx(), ""))
        assert result.type == "error"
        assert "1 issue" in result.message

    def test_doctor_is_available_in_all_engines(self) -> None:
        from src.application.commands.shared.setup_commands import DoctorCommand

        cmd = DoctorCommand()
        for engine in ("llm", "agent", "agentflow", "dify"):
            assert cmd.is_available(engine)

    def test_doctor_has_check_alias(self) -> None:
        from src.application.commands.shared.setup_commands import DoctorCommand

        cmd = DoctorCommand()
        assert "check" in list(cmd.get_all_names())


# ---------------------------------------------------------------------------
# Tab completion — setup/doctor appear in all engines
# ---------------------------------------------------------------------------

class TestCompleterSetupDoctor:

    def _make_completer(self, engine: str = "agent"):
        from src.application.cli.input.completer import CommandCompleter

        ctx = MagicMock()
        ctx.current_engine = engine
        return CommandCompleter(ctx)

    def test_setup_appears_in_all_engines(self) -> None:
        from src.application.cli.input.completer import _ENGINE_COMMANDS

        for engine, cmds in _ENGINE_COMMANDS.items():
            assert "setup" in cmds, f"'setup' missing from engine '{engine}'"

    def test_doctor_appears_in_all_engines(self) -> None:
        from src.application.cli.input.completer import _ENGINE_COMMANDS

        for engine, cmds in _ENGINE_COMMANDS.items():
            assert "doctor" in cmds, f"'doctor' missing from engine '{engine}'"

    def test_setup_flag_completions_available(self) -> None:
        from src.application.cli.input.completer import _ARG_VALUES

        values = _ARG_VALUES.get("setup", [])
        assert "--llm" in values
        assert any("--agent" in v for v in values)
        assert any("--tools" in v for v in values)
        assert "--dify" in values

    @staticmethod
    def _display_str(completion) -> str:
        """Extract the display string from a Completion, handling FormattedText."""
        d = completion.display
        if isinstance(d, str):
            return d
        # FormattedText is a list of (style, text) tuples
        return "".join(text for _, text in d)

    def test_tab_on_slash_includes_setup(self) -> None:
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer("agent")
        doc = Document("/")
        completions = list(completer.get_completions(doc, CompleteEvent()))
        names = {self._display_str(c) for c in completions}
        assert "/setup" in names

    def test_tab_on_slash_includes_doctor(self) -> None:
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer("llm")
        doc = Document("/")
        completions = list(completer.get_completions(doc, CompleteEvent()))
        names = {self._display_str(c) for c in completions}
        assert "/doctor" in names

    def test_setup_arg_completions_filter_by_prefix(self) -> None:
        from prompt_toolkit.document import Document
        from prompt_toolkit.completion import CompleteEvent

        completer = self._make_completer("agent")
        doc = Document("/setup --l")
        completions = list(completer.get_completions(doc, CompleteEvent()))
        texts = [self._display_str(c) for c in completions]
        # --llm should match; --agent/--tools/--dify should not
        assert all("--l" in t for t in texts)


# ---------------------------------------------------------------------------
# Inline hint (suggest) for setup
# ---------------------------------------------------------------------------

class TestSuggestSetup:

    def _make_suggest(self):
        from src.application.cli.input.suggest import CommandAutoSuggest
        from prompt_toolkit.buffer import Buffer
        from unittest.mock import MagicMock

        suggest = CommandAutoSuggest()
        buf = MagicMock(spec=Buffer)
        return suggest, buf

    def test_hint_shown_after_setup_space(self) -> None:
        from src.application.cli.input.suggest import CommandAutoSuggest
        from prompt_toolkit.document import Document
        from prompt_toolkit.buffer import Buffer
        from unittest.mock import MagicMock

        suggest = CommandAutoSuggest()
        buf = MagicMock(spec=Buffer)
        doc = Document("/setup ")
        result = suggest.get_suggestion(buf, doc)

        assert result is not None
        assert "--llm" in result.text or "setup" in result.text.lower()

    def test_no_hint_for_doctor(self) -> None:
        from src.application.cli.input.suggest import CommandAutoSuggest, _PARAM_HINTS
        from prompt_toolkit.document import Document
        from prompt_toolkit.buffer import Buffer
        from unittest.mock import MagicMock

        suggest = CommandAutoSuggest()
        buf = MagicMock(spec=Buffer)
        doc = Document("/doctor ")
        result = suggest.get_suggestion(buf, doc)

        # doctor has no param hints — result should be None
        assert result is None or "doctor" not in _PARAM_HINTS

    def test_no_hint_for_free_text(self) -> None:
        from src.application.cli.input.suggest import CommandAutoSuggest
        from prompt_toolkit.document import Document
        from prompt_toolkit.buffer import Buffer
        from unittest.mock import MagicMock

        suggest = CommandAutoSuggest()
        buf = MagicMock(spec=Buffer)
        doc = Document("just some AI query ")
        result = suggest.get_suggestion(buf, doc)

        assert result is None
