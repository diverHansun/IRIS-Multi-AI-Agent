"""
Logo rendering utilities used by the CLI.

The implementation mirrors ``src/ui/logo/logo.py`` so that the colour scheme,
pyfiglet fonts, and layout remain consistent with the legacy interface.
"""

from __future__ import annotations

import pyfiglet
from rich.console import Console

from src.application.cli.theme import BRAND_COLORS

PRIMARY_COLOUR = BRAND_COLORS["jasmine"]
SECONDARY_COLOUR = BRAND_COLORS["scifi_blue"]


def _get_console(console: Console | None) -> Console:
    return console or Console()


def display_logo(console: Console | None = None) -> None:
    """
    Render the primary IRIS ASCII logo using the ``big`` pyfiglet font.
    """
    target_console = _get_console(console)
    figlet = pyfiglet.Figlet(font="big")
    logo_art = figlet.renderText("IRIS").rstrip()
    target_console.print(logo_art, style=PRIMARY_COLOUR)


def display_logo_intro(console: Console | None = None) -> None:
    """
    Render the introductory banner beneath the main logo using the ``slant`` font.
    """
    target_console = _get_console(console)
    figlet = pyfiglet.Figlet(font="slant")
    intro_art = figlet.renderText("Muti  AI  Agent").rstrip()
    target_console.print(intro_art, style=SECONDARY_COLOUR)
