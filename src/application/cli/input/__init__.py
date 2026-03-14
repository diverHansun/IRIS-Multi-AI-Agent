"""
CLI input layer — prompt_toolkit-based line editing, history, completion, and ghost text.

Public API: create_prompt_input()
This package has no dependency on cli/gui/ components.
Both this package and gui/ are peer modules that serve main.py at the same layer level.
"""

from .session import create_prompt_input

__all__ = ["create_prompt_input"]
