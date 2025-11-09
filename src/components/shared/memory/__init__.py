"""
记忆管理模块

提供全局记忆管理和会话管理功能

Architecture:
- global_memory.py: GlobalMemoryManager for file-based session storage
- session_manager.py: SessionManager for session lifecycle management
- unified_checkpointer.py: UnifiedCheckpointer integrating GlobalMemoryManager with LangGraph
  - Used by both Basic and Deep agent modes for persistent storage
  - Shared storage directory: data/sessions
"""

from .global_memory import GlobalMemoryManager
from .session_manager import SessionManager
from .unified_checkpointer import UnifiedCheckpointer
from .session_context import SessionContext
from .memory_sync import MemorySyncAdapter

__all__ = [
    'GlobalMemoryManager',
    'SessionManager',
    'UnifiedCheckpointer',
    'SessionContext',
    'MemorySyncAdapter',
]
