"""
Base interface for engine adapters.
"""

from __future__ import annotations


class BaseAdapter:
    async def handle_query(self, ctx, query: str):
        """Forward query to the concrete service."""
        raise NotImplementedError
