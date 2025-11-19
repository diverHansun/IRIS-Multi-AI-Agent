"""
Global memory manager providing unified memory management across modes and LLMs.

This module implements a global memory system that supports both shared (basic/llm)
and isolated (deep) agent modes, following SOLID principles.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from ..storage.message_filter import MessageFilter
from ..storage.session_storage import SessionStorage
from .config import (
    BASIC_LLM_STORAGE_DIR,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_AGENT_MODE,
    get_storage_dir,
)

logger = logging.getLogger(__name__)


class GlobalChatMessageHistory(BaseChatMessageHistory):
    """
    Global chat message history implementation.

    Provides LangChain-compatible chat history interface with automatic
    persistence to SessionStorage.
    """

    def __init__(self, session_id: str, global_manager, mode: str = "basic"):
        """
        Initialize global chat message history.

        Args:
            session_id: Session identifier
            global_manager: GlobalMemoryManager instance
            mode: Agent mode ("basic", "llm", "deep")
        """
        self.session_id = session_id
        self.global_manager = global_manager
        self.mode = mode
        self._messages: List[BaseMessage] = []

        # Load historical messages from storage
        self._load_messages()

    @property
    def storage(self):
        """Get the appropriate storage for this history instance."""
        return self.global_manager.get_storage_by_mode(self.mode)

    def _load_messages(self):
        """Load messages from storage."""
        try:
            stored_messages = self.storage.load_session(self.session_id)
            if stored_messages:
                self._messages = stored_messages
                logger.info(f"Loaded session history: {self.session_id} (mode={self.mode}), {len(self._messages)} messages")
        except Exception as e:
            logger.error(f"Failed to load session history: {e}")
            self._messages = []

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add messages to history with automatic persistence."""
        for message in messages:
            self._messages.append(message)

        # Auto-save to storage
        self.global_manager._save_session_async(self.session_id, self._messages, self.mode)

    def clear(self) -> None:
        """Clear message history from memory and storage."""
        self._messages.clear()
        # Synchronously clear storage
        self.storage.delete_session(self.session_id)

    @property
    def messages(self) -> List[BaseMessage]:
        """Get copy of messages list."""
        return self._messages.copy()


class GlobalMemoryManager:
    """
    Global memory manager for unified session management.

    Supports agent mode routing to enable both shared (basic/llm) and isolated (deep)
    memory systems. Follows SRP by focusing solely on memory management.
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        agent_mode: str = DEFAULT_AGENT_MODE,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ):
        """
        Initialize global memory manager.

        Args:
            storage_dir: Storage directory path. If None, auto-resolved from agent_mode
            agent_mode: Agent mode identifier ("basic", "llm", or "deep")
            max_messages: Maximum messages to retain per session

        Raises:
            ValueError: If agent_mode is invalid
        """
        self.agent_mode = agent_mode
        self.max_messages = max_messages
        
        # Initialize storages for different modes
        if storage_dir:
            # Use provided storage_dir (for testing or custom configurations)
            self.shared_storage = SessionStorage(storage_dir)
            self.deep_storage = SessionStorage(storage_dir)
        else:
            # Use default directories from config
            from .config import BASIC_LLM_STORAGE_DIR, DEEP_STORAGE_DIR
            self.shared_storage = SessionStorage(BASIC_LLM_STORAGE_DIR)
            self.deep_storage = SessionStorage(DEEP_STORAGE_DIR)
        
        # Default storage for backward compatibility
        self.storage = self.shared_storage if agent_mode in ["basic", "llm"] else self.deep_storage

        self.message_filter = MessageFilter()

        # In-memory session cache
        self._session_histories: Dict[str, GlobalChatMessageHistory] = {}

        storage_info = storage_dir if storage_dir else f"shared={self.shared_storage.storage_dir}, deep={self.deep_storage.storage_dir}"
        logger.info(
            f"GlobalMemoryManager initialized: mode={agent_mode}, storage={storage_info}"
        )

    def get_storage_by_mode(self, mode: str) -> SessionStorage:
        """Get storage instance for specific agent mode."""
        if mode == "deep":
            return self.deep_storage
        return self.shared_storage
    
    def get_session_history(self, session_id: str, agent_mode: Optional[str] = None) -> BaseChatMessageHistory:
        """
        Get session history (LangChain standard interface).

        Args:
            session_id: Session identifier
            agent_mode: Optional agent mode override. If None, uses default self.agent_mode

        Returns:
            Chat message history instance
        """
        # Create a unique cache key combining session_id and mode
        mode = agent_mode or self.agent_mode
        cache_key = f"{session_id}:{mode}"
        
        if cache_key not in self._session_histories:
            # We need to pass the specific storage to GlobalChatMessageHistory
            # But GlobalChatMessageHistory currently takes global_manager and uses .storage
            # So we need to modify GlobalChatMessageHistory to accept storage or mode
            self._session_histories[cache_key] = GlobalChatMessageHistory(session_id, self, mode)

        return self._session_histories[cache_key]

    def get_message_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        Get message history (compatibility alias).

        Args:
            session_id: Session identifier

        Returns:
            Chat message history instance
        """
        return self.get_session_history(session_id)
    
    def add_conversation(self, session_id: str, user_message: str, ai_response: str,
                        current_llm_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a conversation round to memory.

        Args:
            session_id: Session identifier
            user_message: User message
            ai_response: AI response
            current_llm_info: Current LLM information (optional)

        Returns:
            True if successfully added, False otherwise
        """
        try:
            # Check if this conversation should be saved
            if not self.message_filter.should_save_message(user_message, ai_response):
                logger.debug(f"Filtered system command: {user_message}")
                return False

            # Get session history
            history = self.get_session_history(session_id)

            # Add messages
            messages = [
                HumanMessage(content=user_message),
                AIMessage(content=ai_response)
            ]

            history.add_messages(messages)

            # Trim messages if needed
            self._trim_messages_if_needed(session_id)

            logger.debug(f"Added conversation to session {session_id}: {user_message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to add conversation: {e}")
            return False

    def add_llm_conversation(self, session_id: str, user_message: str, ai_response: str) -> bool:
        """
        Add conversation for LLM mode.

        Args:
            session_id: Session identifier
            user_message: User message
            ai_response: AI response

        Returns:
            True if successfully added, False otherwise
        """
        return self.add_conversation(session_id, user_message, ai_response)
    
    def create_runnable_with_memory(self, runnable, input_key: str = "input", 
                                  history_key: str = "chat_history"):
        """
        Add memory capability to a Runnable object.
        
        Args:
            runnable: The Runnable object to wrap
            input_key: Input key name
            history_key: History key name
            
        Returns:
            Runnable object with memory
        """
        return RunnableWithMessageHistory(
            runnable,
            self.get_session_history,
            input_messages_key=input_key,
            history_messages_key=history_key
        )
    
    def migrate_session_memory(self, old_session_id: str, new_session_id: str) -> bool:
        """
        Migrate session memory (used when switching LLMs).
        
        Args:
            old_session_id: Original session ID
            new_session_id: New session ID
            
        Returns:
            True if migration successful
        """
        try:
            # Get original session history
            old_history = self.get_session_history(old_session_id)
            messages = old_history.messages
            
            if not messages:
                logger.info(f"Original session {old_session_id} has no history, skipping migration")
                return True
            
            # Create new session and copy messages
            new_history = self.get_session_history(new_session_id)
            new_history.add_messages(messages)
            
            logger.info(f"Successfully migrated {len(messages)} messages from {old_session_id} to {new_session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate session memory: {e}")
            return False
    
    def add_context_marker(self, session_id: str, old_provider: str, old_model: str, 
                          new_provider: str, new_model: str, add_marker: bool = False):
        """
        Add model switch context marker.
        
        Args:
            session_id: Session ID
            old_provider: Original provider
            old_model: Original model
            new_provider: New provider
            new_model: New model
            add_marker: Whether to add marker message
        """
        if add_marker:
            user_msg, ai_msg = self.message_filter.create_context_marker(
                old_provider, old_model, new_provider, new_model
            )
            
            history = self.get_session_history(session_id)
            history.add_messages([user_msg, ai_msg])
            
            logger.info(f"Added model switch marker: {old_provider}/{old_model} -> {new_provider}/{new_model}")
    
    def _trim_messages_if_needed(self, session_id: str):
        """Trim message history if needed."""
        try:
            if session_id in self._session_histories:
                history = self._session_histories[session_id]
                messages = history._messages
                
                if len(messages) > self.max_messages:
                    # Keep recent messages, ensuring pairs (User + AI)
                    keep_count = self.max_messages
                    if keep_count % 2 == 1:
                        keep_count -= 1  # Ensure even number to keep pairs intact
                    
                    # Keep from the end
                    history._messages = messages[-keep_count:]
                    
                    # Save to storage
                    self._save_session_async(session_id, history._messages)
                    
                    logger.debug(f"Trimmed session {session_id} history: {len(messages)} -> {len(history._messages)}")
                    
        except Exception as e:
            logger.error(f"Failed to trim message history: {e}")
    
    def save_session(self, session_id: str) -> bool:
        """Save session to storage."""
        try:
            if session_id in self._session_histories:
                history = self._session_histories[session_id]
                messages = history.messages
                self.storage.save_session(session_id, messages)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False
    
    def _save_session_async(self, session_id: str, messages: List[BaseMessage], mode: Optional[str] = None):
        """Async save session (synchronous implementation, interface compatibility)."""
        try:
            storage = self.get_storage_by_mode(mode or self.agent_mode)
            storage.save_session(session_id, messages)
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear session memory.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            # Clear memory cache
            if session_id in self._session_histories:
                self._session_histories[session_id].clear()
                del self._session_histories[session_id]
            
            # Clear storage
            self.storage.delete_session(session_id)
            
            logger.info(f"Successfully cleared session memory: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session memory: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return self.storage.list_sessions()
    
    def session_exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return self.storage.session_exists(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return self.storage.get_session_info(session_id)
    
    def get_conversation_summary(self, session_id: str) -> str:
        """Get conversation summary."""
        try:
            history = self.get_session_history(session_id)
            messages = history.messages
            return self.message_filter.get_conversation_summary(messages)
        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            return "Failed to get summary"
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics."""
        try:
            if session_id in self._session_histories:
                history = self._session_histories[session_id]
                messages = history.messages
                
                human_count = sum(1 for msg in messages if isinstance(msg, HumanMessage))
                ai_count = sum(1 for msg in messages if isinstance(msg, AIMessage))
                
                return {
                    "session_id": session_id,
                    "total_messages": len(messages),
                    "human_messages": human_count,
                    "ai_messages": ai_count,
                    "in_memory": True
                }
            else:
                # Get info from storage
                session_info = self.get_session_info(session_id)
                if session_info:
                    return {
                        "session_id": session_id,
                        "total_messages": session_info.get("message_count", 0),
                        "in_memory": False
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return None

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        try:
            sessions = self.list_sessions()
            total_messages = sum(session.get("message_count", 0) for session in sessions)
            
            return {
                "total_sessions": len(sessions),
                "total_messages": total_messages,
                "active_sessions": len(self._session_histories),
                "max_messages_per_session": self.max_messages,
                "storage_path": str(self.storage.storage_dir)
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"error": str(e)}