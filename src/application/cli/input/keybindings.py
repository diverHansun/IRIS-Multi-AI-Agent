"""
Custom key bindings for the CLI input prompt.

Alt+Enter (Escape, Enter)  — insert a newline without submitting
Ctrl+L                     — clear the screen and redraw the prompt

Note on Shift+Enter:
    prompt_toolkit has no ShiftEnter key (absent from Keys enum).  The VT100
    terminal protocol sends the same byte for Shift+Enter and plain Enter,
    making them indistinguishable.  Alt+Enter (mapped as the 'escape','enter'
    two-key sequence) is the standard prompt_toolkit alternative.

No dependency on AppState or any other application-layer component.
"""

from __future__ import annotations

from prompt_toolkit.key_binding import KeyBindings


def build_key_bindings() -> KeyBindings:
    """Return a configured KeyBindings instance for use in PromptSession."""
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _insert_newline(event) -> None:
        """Alt+Enter: insert a newline character without submitting the input."""
        event.app.current_buffer.insert_text("\n")

    @kb.add("c-l")
    def _clear_screen(event) -> None:
        """Ctrl+L: clear the terminal screen; prompt redraws at the top."""
        event.app.renderer.clear()

    return kb
