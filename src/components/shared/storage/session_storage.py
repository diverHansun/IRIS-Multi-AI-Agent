"""
Session Storage Manager

Provides persistent storage and retrieval of session data.

Design Principles Applied:
- YAGNI: Only persist HumanMessage and AIMessage (real conversations)
- SRP: Single responsibility - manage session file I/O
- KISS: Simple JSON serialization without complex transformations
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)


class SessionStorage:
    """Session storage manager."""
    
    def __init__(self, storage_dir: str = "data/sessions"):
        """
        Initialize session storage manager.
        
        Args:
            storage_dir: Storage directory path
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_index_file = self.storage_dir / "sessions_index.json"
        
        # Load session index
        self.sessions_index = self._load_sessions_index()
    
    def _load_sessions_index(self) -> Dict[str, Dict[str, Any]]:
        """Load session index."""
        try:
            if self.sessions_index_file.exists():
                with open(self.sessions_index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load session index: {e}")
        
        return {}
    
    def _save_sessions_index(self):
        """Save session index."""
        try:
            with open(self.sessions_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session index: {e}")
    
    def _message_to_dict(self, message: BaseMessage) -> Dict[str, Any]:
        """Convert message object to dictionary."""
        return {
            "type": message.__class__.__name__,
            "content": message.content,
            "timestamp": datetime.now().isoformat()
        }
    
    def _dict_to_message(self, msg_dict: Dict[str, Any]) -> BaseMessage:
        """
        Convert dictionary to message object.

        YAGNI Principle: Only deserialize conversational message types (Human/AI).
        SystemMessage and ToolMessage should never be persisted in the first place,
        but we handle them gracefully for backward compatibility.

        Note: ToolMessage and SystemMessage types in old session data are intentionally
        converted to HumanMessage for backward compatibility.
        New sessions should only contain HumanMessage and AIMessage.
        """
        msg_type = msg_dict.get("type", "HumanMessage")
        content = msg_dict.get("content", "")

        if msg_type == "HumanMessage":
            return HumanMessage(content=content)
        elif msg_type == "AIMessage":
            return AIMessage(content=content)
        elif msg_type == "SystemMessage":
            # SystemMessage should not be persisted, but handle gracefully
            logger.warning(
                f"Found SystemMessage in persisted data (should not happen). "
                f"Converting to HumanMessage for compatibility."
            )
            return HumanMessage(content=content)
        elif msg_type == "ToolMessage":
            # ToolMessage should not be persisted, but handle gracefully
            logger.warning(
                f"Found ToolMessage in persisted data (should not happen). "
                f"Converting to HumanMessage for compatibility."
            )
            return HumanMessage(content=content)
        else:
            # Unknown message type - convert to HumanMessage for backward compatibility
            logger.debug(f"Converting unknown message type '{msg_type}' to HumanMessage")
            return HumanMessage(content=content)
    
    def save_session(self, session_id: str, messages: List[BaseMessage], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save session data.
        
        Args:
            session_id: Session ID
            messages: Message list
            metadata: Session metadata
            
        Returns:
            True if successful
        """
        try:
            # Prepare session data
            session_data = {
                "session_id": session_id,
                "messages": [self._message_to_dict(msg) for msg in messages],
                "message_count": len(messages),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # If session exists, keep creation time
            if session_id in self.sessions_index:
                session_data["created_at"] = self.sessions_index[session_id]["created_at"]
            
            # Save session file
            session_file = self.storage_dir / f"{session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # Update index
            self.sessions_index[session_id] = {
                "session_id": session_id,
                "message_count": len(messages),
                "created_at": session_data["created_at"],
                "updated_at": session_data["updated_at"],
                "file_path": str(session_file)
            }
            
            self._save_sessions_index()
            logger.info(f"Session saved successfully: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False
    
    def initialize_empty_session(self, session_id: str) -> bool:
        """
        Initialize empty session file.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            # Create empty session data
            session_data = {
                "session_id": session_id,
                "messages": [],
                "message_count": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": {}
            }
            
            # Save empty session file
            session_file = self.storage_dir / f"{session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # Update index
            self.sessions_index[session_id] = {
                "session_id": session_id,
                "message_count": 0,
                "created_at": session_data["created_at"],
                "updated_at": session_data["updated_at"],
                "file_path": str(session_file)
            }
            
            self._save_sessions_index()
            logger.debug(f"Empty session initialized: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize empty session {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[List[BaseMessage]]:
        """
        Load session data.
        
        Args:
            session_id: Session ID
            
        Returns:
            Message list, or None if session does not exist
        """
        try:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                # Normal for new sessions
                logger.debug(f"Session file not found, will create new session: {session_id}")
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Auto-recover index if missing
            if session_id not in self.sessions_index:
                logger.info(f"Found orphaned session file, recovering index: {session_id}")
                self.sessions_index[session_id] = {
                    "session_id": session_id,
                    "message_count": session_data.get("message_count", len(session_data.get("messages", []))),
                    "created_at": session_data.get("created_at", datetime.now().isoformat()),
                    "updated_at": session_data.get("updated_at", datetime.now().isoformat()),
                    "file_path": str(session_file)
                }
                self._save_sessions_index()
            
            # Convert messages
            messages = []
            for msg_dict in session_data.get("messages", []):
                try:
                    messages.append(self._dict_to_message(msg_dict))
                except Exception as e:
                    logger.warning(f"Failed to convert message: {e}")
                    continue
            
            if len(messages) > 0:
                logger.info(f"Session loaded: {session_id}, {len(messages)} messages")
            else:
                logger.debug(f"Empty session loaded: {session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all user sessions (excluding test sessions).
        
        Returns:
            List of session info, sorted by updated time (most recent first)
        """
        # Filter out test sessions (only include sessions starting with "user_")
        sessions = [
            s for s in self.sessions_index.values()
            if s.get("session_id", "").startswith("user_")
        ]
        # Sort by updated time
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            # Delete session file
            session_file = self.storage_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            # Remove from index
            if session_id in self.sessions_index:
                del self.sessions_index[session_id]
                self._save_sessions_index()
            
            logger.info(f"Session deleted: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if exists
        """
        return session_id in self.sessions_index
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session info dictionary
        """
        return self.sessions_index.get(session_id)
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        Cleanup old sessions.
        
        Args:
            days: Retention days
            
        Returns:
            Number of deleted sessions
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            sessions_to_delete = []
            for session_id, session_info in self.sessions_index.items():
                try:
                    updated_at = datetime.fromisoformat(session_info.get("updated_at", ""))
                    if updated_at < cutoff_date:
                        sessions_to_delete.append(session_id)
                except Exception:
                    continue
            
            # Delete old sessions
            deleted_count = 0
            for session_id in sessions_to_delete:
                if self.delete_session(session_id):
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old sessions")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
    
    def check_session_consistency(self) -> Dict[str, List[str]]:
        """
        Check consistency between index and file system.
        
        Returns:
            Dictionary containing orphaned index entries and files
        """
        try:
            # Get all session files
            session_files = list(self.storage_dir.glob("*.json"))
            session_file_ids = {f.stem for f in session_files if f.name != "sessions_index.json"}
            
            # Get indexed session IDs
            indexed_session_ids = set(self.sessions_index.keys())
            
            # Find orphaned index entries
            orphaned_index_entries = list(indexed_session_ids - session_file_ids)
            
            # Find orphaned files
            orphaned_files = list(session_file_ids - indexed_session_ids)
            
            return {
                "orphaned_index_entries": orphaned_index_entries,
                "orphaned_files": orphaned_files
            }
        except Exception as e:
            logger.error(f"Failed to check session consistency: {e}")
            return {
                "orphaned_index_entries": [],
                "orphaned_files": []
            }
    
    def cleanup_orphaned_sessions(self) -> Dict[str, int]:
        """
        Cleanup orphaned session files and index entries.
        
        Returns:
            Cleanup statistics
        """
        try:
            consistency = self.check_session_consistency()
            cleaned_count = {
                "orphaned_index_entries": 0,
                "orphaned_files": 0
            }
            
            # Cleanup orphaned index entries
            for session_id in consistency["orphaned_index_entries"]:
                if session_id in self.sessions_index:
                    del self.sessions_index[session_id]
                    cleaned_count["orphaned_index_entries"] += 1
            
            # Cleanup orphaned files
            for session_id in consistency["orphaned_files"]:
                session_file = self.storage_dir / f"{session_id}.json"
                if session_file.exists():
                    session_file.unlink()
                    cleaned_count["orphaned_files"] += 1
            
            # Save index if changes made
            if sum(cleaned_count.values()) > 0:
                self._save_sessions_index()
                logger.info(f"Cleaned up {cleaned_count['orphaned_index_entries']} orphaned index entries and {cleaned_count['orphaned_files']} orphaned files")
            
            return cleaned_count
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned sessions: {e}")
            return {
                "orphaned_index_entries": 0,
                "orphaned_files": 0
            }