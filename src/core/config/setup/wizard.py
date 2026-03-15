"""
SetupWizard -- Main orchestrator for the IRIS setup wizard.

Manages the setup flow: first-time, upgrade detection, manual re-run.
Reads/writes the [setup] section in config.toml via tomlkit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from src.core.config.setup.steps.base import SetupContext, SetupStep
from src.core.config.setup.steps.llm import LLMSetupStep
from src.core.config.setup.steps.agent import AgentSetupStep
from src.core.config.setup.steps.tools import ToolsSetupStep
from src.core.config.setup.steps.dify import DifySetupStep
from src.core.config.setup.writer import EnvWriter

logger = logging.getLogger(__name__)

# Core-layer color constants (no dependency on application layer)
_COLORS: Dict = {
    "info": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "text_dim": "dim",
}


def _get_colors() -> Dict:
    return _COLORS


def get_package_version() -> str:
    """Get version from installed package metadata or pyproject.toml."""
    try:
        from importlib.metadata import version
        return version("iris-muti-ai-agent")
    except Exception:
        pass

    # Fallback: read pyproject.toml directly (dev mode)
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return "0.0.0"

    pyproject = Path(__file__).resolve().parents[4] / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return data.get("project", {}).get("version", "0.0.0")
        except Exception:
            pass
    return "0.0.0"


def _version_lt(installed: str, current: str) -> bool:
    """Compare semantic versions safely."""
    try:
        from packaging.version import Version
        return Version(installed) < Version(current)
    except Exception:
        return installed != current


class SetupWizard:
    """Main orchestrator for the setup wizard."""

    def __init__(self, share_dir: Optional[Path] = None, console: Optional[Console] = None):
        self._share_dir = share_dir or Path.home() / ".iris"
        self._console = console or Console()
        self._env_writer = EnvWriter(self._share_dir / ".env")

    def check_and_run(self) -> bool:
        """Auto-check at startup, run wizard if needed."""
        setup_info = self._read_setup_info()

        if not setup_info.get("completed", False):
            return self.run_first_time()

        installed_ver = setup_info.get("version", "0.0.0")
        current_ver = get_package_version()
        if _version_lt(installed_ver, current_ver):
            self._print_upgrade_hint(installed_ver, current_ver)

        return True

    def run_first_time(self) -> bool:
        """Full wizard for first-time setup."""
        context = self._build_context()

        try:
            self._print_welcome_banner(context.version)

            steps = self._get_all_steps()

            for i, step in enumerate(steps, 1):
                self._print_step_header(i, len(steps), step.title)
                result = step.run(context)

                if result.skipped:
                    self._print_skip_message(step.name)
                elif result.error:
                    self._print_error(result.error)
                    if not step.skippable:
                        return False

            self._print_summary(context)
            self._mark_completed(context.version)
            return True

        except KeyboardInterrupt:
            self._console.print(
                "\nSetup interrupted. Run /iris setup to continue.",
                style=_get_colors()["warning"],
            )
            return False

    def run_all(self) -> bool:
        """Manual /iris setup with no args: run all steps.

        Unlike run_first_time(), this does NOT update completed_at,
        preserving the original first-time setup record.
        It does update version to the current version.
        """
        context = self._build_context()

        try:
            self._print_welcome_banner(context.version)

            steps = self._get_all_steps()

            for i, step in enumerate(steps, 1):
                self._print_step_header(i, len(steps), step.title)
                result = step.run(context)

                if result.skipped:
                    self._print_skip_message(step.name)
                elif result.error:
                    self._print_error(result.error)
                    if not step.skippable:
                        return False

            self._print_summary(context)
            self._update_version(context.version)
            return True

        except KeyboardInterrupt:
            self._console.print(
                "\nSetup interrupted.",
                style=_get_colors()["warning"],
            )
            return False

    def run_specific(self, target: str, sub_target: Optional[str] = None) -> bool:
        """Run a specific step: e.g., target='llm', target='tools', sub_target='mcp'."""
        step = self._resolve_step(target)
        if step is None:
            self._console.print(f"Unknown setup target: {target}", style=_get_colors()["error"])
            return False

        context = self._build_context()

        try:
            result = step.run(context, sub_target=sub_target)
            if result.error:
                self._print_error(result.error)
                return False
            return True

        except KeyboardInterrupt:
            self._console.print("\nSetup interrupted.", style=_get_colors()["warning"])
            return False

    # ---- Private helpers ----

    def _get_all_steps(self) -> list:
        return [
            LLMSetupStep(),
            AgentSetupStep(),
            ToolsSetupStep(),
            DifySetupStep(),
        ]

    def _resolve_step(self, target: str) -> Optional[SetupStep]:
        """Resolve step name to step instance."""
        step_map = {
            "llm": LLMSetupStep,
            "agent": AgentSetupStep,
            "tools": ToolsSetupStep,
            "dify": DifySetupStep,
        }
        cls = step_map.get(target)
        return cls() if cls else None

    def _build_context(self) -> SetupContext:
        env_writer = EnvWriter(self._share_dir / ".env")
        pre_configured = set(env_writer.get_configured_providers())
        return SetupContext(
            share_dir=self._share_dir,
            env_writer=env_writer,
            configured_providers=pre_configured,
            console=self._console,
            version=get_package_version(),
        )

    def _read_setup_info(self) -> dict:
        """Read [setup] section from config.toml."""
        config_path = self._share_dir / "config.toml"
        if not config_path.exists():
            return {}
        try:
            import tomlkit
            content = config_path.read_text(encoding="utf-8")
            doc = tomlkit.parse(content)
            setup_section = doc.get("setup", {})
            return dict(setup_section)
        except Exception as exc:
            logger.warning("Failed to read [setup] from config.toml: %s", exc)
            return {}

    def _mark_completed(self, version: str) -> None:
        """Write [setup] section to config.toml."""
        self._write_setup_section({
            "completed": True,
            "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            "version": version,
        })

    def _update_version(self, version: str) -> None:
        """Update only the version field in [setup] section."""
        current = self._read_setup_info()
        current["version"] = version
        self._write_setup_section(current)

    def _write_setup_section(self, data: dict) -> None:
        """Write [setup] section to config.toml using tomlkit."""
        config_path = self._share_dir / "config.toml"
        try:
            import tomlkit

            if config_path.exists():
                content = config_path.read_text(encoding="utf-8")
                doc = tomlkit.parse(content)
            else:
                doc = tomlkit.document()

            if "setup" not in doc:
                doc.add(tomlkit.nl())
                doc.add(tomlkit.comment(
                    "Setup Wizard State (managed automatically, do not edit manually)"
                ))

            doc["setup"] = data
            config_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

        except Exception as exc:
            logger.warning("Failed to write [setup] to config.toml: %s", exc)

    def _print_welcome_banner(self, version: str) -> None:
        colors = _get_colors()
        self._console.print()
        self._console.print(Panel(
            Text("IRIS Setup Wizard", style="bold"),
            subtitle=f"v{version}",
            border_style=colors["info"],
            padding=(1, 2),
        ))

    def _print_step_header(self, step_num: int, total: int, title: str) -> None:
        colors = _get_colors()
        self._console.print()
        self._console.print(Rule(
            f"Step {step_num}/{total}: {title}",
            style=colors["info"],
        ))

    def _print_skip_message(self, step_name: str) -> None:
        colors = _get_colors()
        self._console.print(f"  [-] {step_name} skipped", style=colors["text_dim"])

    def _print_error(self, message: str) -> None:
        colors = _get_colors()
        self._console.print(f"  [x] {message}", style=colors["error"])

    def _print_summary(self, context: SetupContext) -> None:
        colors = _get_colors()
        providers = ", ".join(sorted(context.configured_providers)) or "none"
        summary = f"Configured providers: {providers}"
        self._console.print()
        self._console.print(Panel(
            summary,
            title="Setup Complete",
            border_style=colors["success"],
            padding=(1, 2),
        ))

    def _print_upgrade_hint(self, old_ver: str, new_ver: str) -> None:
        colors = _get_colors()
        self._console.print(
            f"IRIS has been updated to v{new_ver} (was v{old_ver}).\n"
            f"New configuration options may be available.\n"
            f"Run /iris setup to configure.",
            style=colors["info"],
        )
