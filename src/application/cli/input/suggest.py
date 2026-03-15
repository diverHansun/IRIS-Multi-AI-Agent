"""
Inline parameter ghost text (auto-suggestion).

After the user types a complete command name followed by a space, a dim
suggestion text appears to the right of the cursor showing the expected
parameter format — similar to fish shell inline hints.

Rules:
  - Only active for lines starting with /
  - Only shown when the cursor is at a trailing space (the user is about to
    type an argument, not in the middle of one)
  - Advances through hint stages as more arguments are filled in
  - Free-text AI queries are completely unaffected

No dependency on AppState or gui/ components — pure text parsing.
"""

from __future__ import annotations

from typing import Optional

from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document


# Parameter hint table.
# Key: command name without the leading slash.
# Value: list of hint strings indexed by the number of arguments already filled.
#   index 0 -> no arguments yet (shown right after "/<cmd> ")
#   index 1 -> one argument filled (shown after "/<cmd> <arg1> ")
_PARAM_HINTS: dict[str, list[str]] = {
    "model":          ["<provider> [model]", "[model]"],
    "switch":         ["llm | agent | agentflow | dify"],
    "mode":           ["basic | deep"],
    "stream":         ["on | off"],
    "use":            ["research | coding | analysis"],
    "restore":        ["<session_id>"],
    "delete_session": ["<session_id>"],
    "skills":         ["list | create <name> | info <name> | reload", "<name> [--project]"],
    "mcp":            ["status [-v] | tools [--json] | reload"],
    "connector":      ["status [-v] | tools [--json] | reload"],
    "deep":           ["status | config reload | filesystem status | filesystem reload"],
    "files":          ["clear | remove <index>"],
    "upload":         ["<file_path>"],
    "sessions":       ["[all]"],
    "setup":          ["--llm | --agent [basic|deep] | --tools [sdk|mcp] | --dify"],
}


class CommandAutoSuggest(AutoSuggest):
    """Display inline parameter hints for known CLI commands.

    Activated in PromptSession via auto_suggest=CommandAutoSuggest().
    The suggestion renders as dim ghost text; it does not modify the buffer.
    """

    def get_suggestion(self, buffer: Buffer, document: Document) -> Optional[Suggestion]:
        text = document.text_before_cursor.lstrip()

        if not text.startswith("/"):
            return None

        # Only show when the cursor sits at a trailing space, meaning the user
        # has finished typing the previous token and is about to start a new one.
        if not text.endswith(" "):
            return None

        parts = text[1:].split(" ")
        cmd_name = parts[0]

        hints = _PARAM_HINTS.get(cmd_name)
        if hints is None:
            return None

        # Number of arguments already provided = total tokens - command name - trailing empty slot.
        filled = max(0, len(parts) - 2)
        hint_index = min(filled, len(hints) - 1)

        return Suggestion(hints[hint_index])
