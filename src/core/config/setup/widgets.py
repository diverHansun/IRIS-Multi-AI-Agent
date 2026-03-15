"""
Interactive selector widgets for the setup wizard.

Uses prompt_toolkit for keyboard-driven interaction and Rich for static output.
The two libraries never render concurrently to avoid terminal conflicts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout

logger = logging.getLogger(__name__)

# prompt_toolkit ANSI styles mapped to project theme
PT_STYLES = {
    "highlight": "bold ansibrightcyan",
    "configured": "ansibrightgreen",
    "not_configured": "ansigray",
    "hint": "italic ansigray",
    "disabled": "ansigray",
}


@dataclass
class Option:
    """A single selectable option."""

    key: str
    label: str
    description: str
    status: str = ""
    disabled: bool = False


class SelectOne:
    """Single-select list with keyboard navigation."""

    def __init__(
        self,
        title: str,
        options: List[Option],
        default: Optional[str] = None,
    ):
        self._title = title
        self._options = options
        self._cursor = 0
        self._result: Optional[Option] = None
        self._cancelled = False

        if default:
            for i, opt in enumerate(options):
                if opt.key == default:
                    self._cursor = i
                    break

    def run(self) -> Optional[Option]:
        """Block until user selects an option. Returns selected Option or None."""
        if not self._options:
            return None

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("pageup")
        def _up(event):
            self._move_cursor(-1)

        @kb.add("down")
        @kb.add("pagedown")
        def _down(event):
            self._move_cursor(1)

        @kb.add("enter")
        def _select(event):
            opt = self._options[self._cursor]
            if not opt.disabled:
                self._result = opt
                event.app.exit()

        @kb.add("q")
        @kb.add("escape")
        def _cancel(event):
            self._cancelled = True
            event.app.exit()

        control = FormattedTextControl(self._get_formatted_text)
        hint_control = FormattedTextControl(
            FormattedText([("class:hint", "  [PgUp/PgDn] Navigate  [Enter] Select  [q] Cancel")])
        )

        layout = Layout(
            HSplit([
                Window(content=control, wrap_lines=False),
                Window(content=hint_control, height=1),
            ])
        )

        app: Application = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
        )

        print(f"\n  {self._title}\n")
        app.run()

        return self._result

    def _move_cursor(self, delta: int) -> None:
        """Move cursor skipping disabled items."""
        size = len(self._options)
        new_pos = self._cursor + delta
        while 0 <= new_pos < size:
            if not self._options[new_pos].disabled:
                self._cursor = new_pos
                return
            new_pos += delta
        # If out of bounds, stay at current

    def _get_formatted_text(self) -> FormattedText:
        fragments = []
        for i, opt in enumerate(self._options):
            is_current = i == self._cursor
            prefix = "  > " if is_current else "    "
            label_style = PT_STYLES["highlight"] if is_current else ""
            if opt.disabled:
                label_style = PT_STYLES["disabled"]

            # Build line: prefix + label + description + status
            label_part = f"{opt.label:<12}"
            desc_part = f"{opt.description:<45}"
            status_part = opt.status

            status_style = ""
            if "configured" in status_part.lower() or "available" in status_part.lower():
                status_style = PT_STYLES["configured"]
            elif "not configured" in status_part.lower():
                status_style = PT_STYLES["not_configured"]

            fragments.append((label_style, prefix + label_part))
            fragments.append((label_style if is_current else "", desc_part))
            fragments.append((status_style, status_part))
            fragments.append(("", "\n"))

        return FormattedText(fragments)


class SelectMany:
    """Multi-select list with keyboard navigation and toggle."""

    def __init__(
        self,
        title: str,
        options: List[Option],
        pre_selected: Optional[List[str]] = None,
    ):
        self._title = title
        self._options = options
        self._cursor = 0
        self._selected: set = set(pre_selected or [])
        self._cancelled = False

    def run(self) -> List[Option]:
        """Block until user confirms. Returns list of selected Options."""
        if not self._options:
            return []

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("pageup")
        def _up(event):
            if self._cursor > 0:
                self._cursor -= 1

        @kb.add("down")
        @kb.add("pagedown")
        def _down(event):
            if self._cursor < len(self._options) - 1:
                self._cursor += 1

        @kb.add("space")
        def _toggle(event):
            opt = self._options[self._cursor]
            if not opt.disabled:
                if opt.key in self._selected:
                    self._selected.discard(opt.key)
                else:
                    self._selected.add(opt.key)

        @kb.add("enter")
        def _confirm(event):
            event.app.exit()

        @kb.add("a")
        def _select_all(event):
            for opt in self._options:
                if not opt.disabled:
                    self._selected.add(opt.key)

        @kb.add("n")
        def _select_none(event):
            self._selected.clear()

        @kb.add("q")
        @kb.add("escape")
        def _cancel(event):
            self._cancelled = True
            self._selected.clear()
            event.app.exit()

        control = FormattedTextControl(self._get_formatted_text)
        hint_control = FormattedTextControl(
            FormattedText([("class:hint",
                           "  [PgUp/PgDn] Navigate  [Space] Toggle  [Enter] Confirm  [a] All  [n] None")])
        )

        layout = Layout(
            HSplit([
                Window(content=control, wrap_lines=False),
                Window(content=hint_control, height=1),
            ])
        )

        app: Application = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
        )

        print(f"\n  {self._title}\n")
        app.run()

        return [opt for opt in self._options if opt.key in self._selected]

    def _get_formatted_text(self) -> FormattedText:
        fragments = []
        for i, opt in enumerate(self._options):
            is_current = i == self._cursor
            is_selected = opt.key in self._selected
            prefix = "  > " if is_current else "    "
            checkbox = "[x]" if is_selected else "[ ]"
            label_style = PT_STYLES["highlight"] if is_current else ""

            label_part = f"{opt.label:<18}"
            desc_part = f"{opt.description:<22}"
            status_part = opt.status

            status_style = ""
            if "configured" in status_part.lower() or "available" in status_part.lower():
                status_style = PT_STYLES["configured"]
            elif "not configured" in status_part.lower():
                status_style = PT_STYLES["not_configured"]

            fragments.append((label_style, f"{prefix}{checkbox} {label_part}"))
            fragments.append(("", desc_part))
            fragments.append((status_style, status_part))
            fragments.append(("", "\n"))

        return FormattedText(fragments)
