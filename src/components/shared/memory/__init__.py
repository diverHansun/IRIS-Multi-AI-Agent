"""
Memory Management Module

Provides global memory management and session lifecycle services.

Architecture:
- global_memory.py: GlobalMemoryManager for managing storage instances (Shared/Deep)
- session_manager.py: SessionManager for session lifecycle management (Create/Switch/Clear)
- memory_sync.py: MemorySyncAdapter for syncing Runtime (LangGraph) and Storage (File)
- session_context.py: SessionContext for passing session metadata
"""

from .global_memory import GlobalMemoryManager
from .session_manager import SessionManager
from .session_context import SessionContext
from .memory_sync import MemorySyncAdapter

__all__ = [
    'GlobalMemoryManager',
    'SessionManager',
    'SessionContext',
    'MemorySyncAdapter',
]
