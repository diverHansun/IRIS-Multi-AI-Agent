"""Structured transcript events for terminal renderers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    """A semantic terminal transcript event."""

    kind: str
    text: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

