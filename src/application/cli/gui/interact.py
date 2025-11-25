"""
User interaction helpers for the CLI GUI.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from rich.console import Console

from src.application.cli.theme import COLORS


def prompt_confirm(console: Console, message: str, default: bool = False) -> bool:
    """
    Prompt the user for a yes/no confirmation.
    """
    suffix = "[Y/n]" if default else "[y/N]"
    response = console.input(f"{message} {suffix} ").strip().lower()
    if not response:
        return default
    return response in {"y", "yes"}


def prompt_select(console: Console, options: Sequence[str], title: str = "") -> str:
    """
    Prompt the user to select an item from a list of options.
    """
    if not options:
        raise ValueError("No options available for selection.")
    console.print(title or "Select an option:")
    for index, option in enumerate(options, start=1):
        console.print(f"{index}. {option}")
    while True:
        choice = console.input("Enter number: ").strip()
        if not choice.isdigit():
            console.print("Invalid input, please enter a number", style=COLORS["error"])
            continue
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
        console.print("Selection out of range, try again", style=COLORS["error"])


def parse_indices(value: str) -> list[int]:
    """
    Parse a whitespace separated list of indices (1-based) into integers.
    """
    indices: list[int] = []
    for token in value.split():
        if token.isdigit():
            indices.append(int(token) - 1)
    return indices
