#!/usr/bin/env python3
"""
Test runner for Multi-AI-Agent.

This script provides stable test suite aliases and runs pytest via
`python -m pytest` for better cross-platform reliability.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class SuiteSpec:
    paths: List[str]
    pytest_args: List[str] = field(default_factory=list)
    description: str = ""


SUITES: Dict[str, SuiteSpec] = {
    "all": SuiteSpec(
        paths=["tests"],
        pytest_args=["--tb=short"],
        description="Run all tests.",
    ),
    "unit": SuiteSpec(
        paths=["tests/unit"],
        description="Run all unit tests.",
    ),
    "integration": SuiteSpec(
        paths=["tests/integration"],
        description="Run all integration tests.",
    ),
    "application": SuiteSpec(
        paths=["tests/unit/application", "tests/integration/test_command_dispatch_integration.py",
               "tests/integration/test_adapter_service_integration.py",
               "tests/integration/test_engine_switch_command_integration.py"],
        description="Run application-layer routing/command/service tests.",
    ),
    "memory": SuiteSpec(
        paths=["tests/unit/memory", "tests/unit/memory-storage", "tests/integration/test_session_storage.py"],
        description="Run memory and session persistence related tests.",
    ),
    "tools": SuiteSpec(
        paths=["tests/unit/tools"],
        description="Run tools-related unit tests.",
    ),
    "deepagents": SuiteSpec(
        paths=["tests/unit/deepagents", "tests/integration/test_hitl_execute_shell.py"],
        description="Run deep-agent and HITL related tests.",
    ),
    "timeout": SuiteSpec(
        paths=["tests/unit/timeout"],
        description="Run timeout/recovery tests.",
    ),
    "quick": SuiteSpec(
        paths=["tests/unit/application", "tests/unit/core", "tests/unit/memory", "tests/unit/tools"],
        description="Run a quick local smoke suite.",
    ),
}

# Backward compatible aliases from the deprecated script.
LEGACY_ALIASES: Dict[str, str] = {
    "ollama": "integration",
    "mcp": "tools",
}


def _resolve_python_executable() -> str:
    """
    Resolve Python interpreter for running pytest.

    Priority:
    1) TEST_RUNNER_PYTHON env override
    2) Project local virtualenv (.venv/venv)
    3) Current interpreter (sys.executable)
    """
    explicit = os.getenv("TEST_RUNNER_PYTHON")
    if explicit:
        return explicit

    candidates = [
        Path(".venv/Scripts/python.exe"),
        Path("venv/Scripts/python.exe"),
        Path(".venv/bin/python"),
        Path("venv/bin/python"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return sys.executable


def _resolve_existing_paths(paths: List[str]) -> List[str]:
    existing: List[str] = []
    for item in paths:
        if Path(item).exists():
            existing.append(item)
    return existing


def _build_parser() -> argparse.ArgumentParser:
    available = sorted(list(SUITES.keys()) + list(LEGACY_ALIASES.keys()))
    parser = argparse.ArgumentParser(description="Multi-AI-Agent test runner")
    parser.add_argument(
        "--type",
        choices=available,
        default="all",
        help="Test suite to run.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose pytest output.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Shortcut for --type quick.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suites and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pytest command without executing.",
    )
    return parser


def _print_suites() -> None:
    print("Available suites:")
    for name in sorted(SUITES.keys()):
        print(f"  - {name:12} {SUITES[name].description}")
    if LEGACY_ALIASES:
        print("\nLegacy aliases:")
        for alias, target in LEGACY_ALIASES.items():
            print(f"  - {alias:12} -> {target}")


def main() -> int:
    parser = _build_parser()
    args, passthrough = parser.parse_known_args()

    if args.list:
        _print_suites()
        return 0

    suite_name = "quick" if args.fast else args.type
    if suite_name in LEGACY_ALIASES:
        mapped = LEGACY_ALIASES[suite_name]
        print(f"[INFO] Suite '{suite_name}' is deprecated, mapped to '{mapped}'.")
        suite_name = mapped

    spec = SUITES[suite_name]
    paths = _resolve_existing_paths(spec.paths)
    if not paths:
        print(f"[ERROR] No test paths exist for suite '{suite_name}'.")
        print(f"Configured paths: {spec.paths}")
        return 1

    python_exe = _resolve_python_executable()
    cmd: List[str] = [python_exe, "-m", "pytest", *paths, *spec.pytest_args]
    if args.verbose:
        cmd.append("-v")
    if passthrough:
        cmd.extend(passthrough)

    print(f"Running suite: {suite_name}")
    print("Command:", " ".join(cmd))

    if args.dry_run:
        return 0

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("[SUCCESS] Tests passed.")
    else:
        print("[FAILED] Tests failed.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
