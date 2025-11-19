"""
Session Manager

Provides advanced session management features like creation, switching, and recovery.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from rich.console import Console

from .global_memory import GlobalMemoryManager

console = Console()

logger = logging.getLogger(__name__)


class SessionManager:
    """Session manager providing advanced session lifecycle management."""
    
    def __init__(self, memory_manager: GlobalMemoryManager, mode: str = "basic"):
        """
        Initialize session manager.
        
        Args:
            memory_manager: Global memory manager instance
            mode: Agent mode ("basic", "llm", "deep")
        """
        self.memory_manager = memory_manager
        self.mode = mode
        self.current_session_id: Optional[str] = None
        
        logger.info(f"Session manager initialized (mode={mode})")

    @property
    def storage(self):
        """Get storage instance for current mode."""
        return self.memory_manager.get_storage_by_mode(self.mode)
    
    def create_new_session(self, user_prefix: str = "user") -> str:
        """
        Create a new session.
        
        Args:
            user_prefix: User prefix for session ID
            
        Returns:
            New session ID
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        session_id = f"{user_prefix}_{timestamp}_{unique_id}"
        
        self.current_session_id = session_id
        
        # Initialize empty session file immediately to avoid warnings later
        self.storage.initialize_empty_session(session_id)
        
        console.print(f"[dim]Created new session: {session_id}[/]")
        
        return session_id
    
    def get_or_create_default_session(self) -> str:
        """
        Get or create default session (always restores most recent).
        
        Returns:
            Session ID
        """
        if not self.current_session_id:
            # Try to restore recent session
            recent_session = self.get_most_recent_session()
            if recent_session:
                self.current_session_id = recent_session["session_id"]
                console.print(f"[dim]Loaded recent session: {self.current_session_id}[/]")
            else:
                # Create new session
                self.current_session_id = self.create_new_session()
            
        return self.current_session_id
    
    def prompt_for_session_choice(self) -> str:
        """
        Prompt user to choose between creating new session or restoring recent one.
        
        Returns:
            Session ID
        """
        if self.current_session_id:
            return self.current_session_id
            
        # Check for recent session
        recent_session = self.get_most_recent_session()
        
        if recent_session:
            # Display recent session info
            session_id = recent_session["session_id"]
            msg_count = recent_session.get("message_count", 0)
            created_time = recent_session.get("created_at", "")[:19] if recent_session.get("created_at") else "Unknown"
            
            console.print(f"[yellow]Found recent session:[/]")
            console.print(f"[dim]  Session ID: {session_id}[/]")
            console.print(f"[dim]  Messages: {msg_count}[/]")
            console.print(f"[dim]  Created: {created_time}[/]")
            
            # Prompt user
            try:
                choice = console.input("\n[cyan]Choose action: [1]Restore recent [2]Create new (Default:1): [/]").strip()
                if choice == "2":
                    self.current_session_id = self.create_new_session()
                    console.print("[green]Created new conversation session[/]")
                else:
                    self.current_session_id = session_id
                    console.print(f"[green]Restored recent session: {session_id}[/]")
                    # Show summary
                    summary = self.get_current_session_summary()
                    if summary != "No conversation history":
                        console.print(f"[dim]Summary: {summary}[/]")
            except (KeyboardInterrupt, EOFError):
                # Default to restore
                self.current_session_id = session_id
                console.print(f"[dim]Defaulting to restore recent session: {session_id}[/]")
        else:
            # No history, create new
            self.current_session_id = self.create_new_session()
            console.print("[green]First run, created new session[/]")
        
        return self.current_session_id
    
    def switch_to_session(self, session_id: str) -> bool:
        """
        Switch to specified session.
        
        Args:
            session_id: Target session ID
            
        Returns:
            True if successful
        """
        if not self.memory_manager.session_exists(session_id):
            logger.error(f"Session does not exist: {session_id}")
            return False
        
        old_session = self.current_session_id
        self.current_session_id = session_id
        
        logger.info(f"Switched session: {old_session} -> {session_id}")
        return True
    
    def get_most_recent_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent session.
        
        Returns:
            Recent session info, or None
        """
        sessions = self.memory_manager.list_sessions()
        if sessions:
            return sessions[0]  # Already sorted by updated time
        return None
    
    def migrate_to_new_session_for_llm_switch(self, old_provider: str, old_model: str, 
                                            new_provider: str, new_model: str, 
                                            preserve_history: bool = True) -> str:
        """
        Create new session for LLM switch and migrate history if needed.
        
        Args:
            old_provider: Old LLM provider
            old_model: Old model
            new_provider: New LLM provider
            new_model: New model
            preserve_history: Whether to preserve history
            
        Returns:
            New session ID
        """
        old_session_id = self.current_session_id
        
        if preserve_history and old_session_id:
            # Use same session ID to keep continuity
            logger.info(f"LLM switch keeping session continuity: {old_provider}/{old_model} -> {new_provider}/{new_model}")
            return old_session_id
        else:
            # Create new session
            new_session_id = self.create_new_session()
            
            if preserve_history and old_session_id:
                # Migrate history
                self.memory_manager.migrate_session_memory(old_session_id, new_session_id)
            
            logger.info(f"LLM switch created new session: {new_session_id}")
            return new_session_id
    
    def get_current_session_summary(self) -> str:
        """
        Get current session summary.
        
        Returns:
            Session summary
        """
        if not self.current_session_id:
            return "No active session"
        
        return self.memory_manager.get_conversation_summary(self.current_session_id)
    
    def clear_current_session(self) -> bool:
        """
        Clear current session.
        
        Returns:
            True if successful
        """
        if not self.current_session_id:
            return False
        
        success = self.memory_manager.clear_session(self.current_session_id)
        if success:
            logger.info(f"Cleared current session: {self.current_session_id}")
        
        return success
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = self.memory_manager.get_memory_stats()
        stats.update({
            "current_session_id": self.current_session_id,
            "current_session_summary": self.get_current_session_summary() if self.current_session_id else None
        })
        
        return stats
    
    def validate_session_id(self, session_id: str) -> bool:
        """
        Validate session ID format.
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            True if valid
        """
        if not session_id or not isinstance(session_id, str):
            return False
        
        # Basic format check
        parts = session_id.split('_')
        if len(parts) < 3:
            return False
        
        return True
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Cleanup old sessions.
        
        Args:
            days: Retention days
            
        Returns:
            Number of cleaned sessions
        """
        try:
            return self.storage.cleanup_old_sessions(days)
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
    
    def check_session_consistency(self) -> Dict[str, List[str]]:
        """
        Check session consistency.
        
        Returns:
            Dictionary with orphaned entries
        """
        try:
            return self.storage.check_session_consistency()
        except Exception as e:
            logger.error(f"Failed to check session consistency: {e}")
            return {
                "orphaned_index_entries": [],
                "orphaned_files": []
            }
    
    def cleanup_orphaned_sessions(self) -> Dict[str, int]:
        """
        Cleanup orphaned sessions.
        
        Returns:
            Cleanup statistics
        """
        try:
            return self.storage.cleanup_orphaned_sessions()
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned sessions: {e}")
            return {
                "orphaned_index_entries": 0,
                "orphaned_files": 0
            }