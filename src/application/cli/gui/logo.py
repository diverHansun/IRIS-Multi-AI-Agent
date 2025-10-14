"""
Logo rendering helpers migrated from ``src/ui/logo/logo.py``.
"""

from __future__ import annotations

from rich.console import Console


def display_logo(console: Console | None = None) -> None:
    """
    Display the startup logo. The ASCII art is migrated during the refactor.
    """
    target_console = console or Console()
    target_console.print("[bold magenta]IRIS[/] :: Multi-AI-Agent")


def display_logo_intro(console: Console | None = None) -> None:
    """
    Display supplementary introduction text for the logo.
    """
    target_console = console or Console()
    target_console.print("[dim]Initializing systems...[/]")

