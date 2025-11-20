"""
Message Filter

Filters system commands and retains only real user conversations and AI responses.

Design Principles Applied:
- KISS: Use message types instead of content pattern matching for system notifications
- SRP: Single responsibility - filter messages based on clear type criteria
- DRY: Centralized filtering logic without duplication
"""

import re
from typing import List, Dict, Any, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage


class MessageFilter:
    """Message filter for filtering system commands and retaining conversation content."""
    
    # System commands to filter (supports both with and without / prefix)
    SYSTEM_COMMANDS = {
        'help', '/help', 'info', '/info', 
        'llms', '/llms', 'llm', '/llm',
        'clear', '/clear', 'reset', '/reset',
        'sessions', '/sessions', 'ls', '/ls',
        'exit', '/exit', 'quit', '/quit',
        'new', '/new', 'upload', '/upload',
        'files', '/files', 'clearfiles', '/clearfiles',
        'reload', '/reload', 'cleanup', '/cleanup',
        'reconnect', '/reconnect'
    }
    
    # Command prefix patterns (supports both with and without / prefix)
    COMMAND_PREFIXES = [
        r'^/?switch\s+',      # switch openai gpt-4o or /switch openai gpt-4o
        r'^/?mode\s+',        # mode llm/agent or /mode llm/agent
        r'^/?stream\s+',      # stream on/off or /stream on/off
        r'^/?restore\s+',     # restore session_id or /restore session_id
        r'^/?mcp\s+',         # mcp status/tools/reload or /mcp status/tools/reload
        r'^/?delete_session\s+',  # delete_session session_id or /delete_session session_id
    ]
    
    def __init__(self):
        """Initialize message filter."""
        self.command_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.COMMAND_PREFIXES]
    
    def is_system_command(self, message: str) -> bool:
        """
        Check if the message is a system command.
        
        Args:
            message: User message content
            
        Returns:
            True if it is a system command, False otherwise
        """
        message = message.strip()
        message_lower = message.lower()
        
        # Check exact match system commands
        if message_lower in self.SYSTEM_COMMANDS:
            return True
        
        # Check command prefix patterns
        for pattern in self.command_patterns:
            if pattern.match(message_lower):
                return True
        
        return False
    
    def should_save_message(self, user_message: str, ai_response: str = "") -> bool:
        """
        Determine if the conversation should be saved to memory.
        
        Args:
            user_message: User message
            ai_response: AI response
            
        Returns:
            True if it should be saved, False otherwise
        """
        # Filter system commands
        if self.is_system_command(user_message):
            return False
        
        # Filter empty messages
        if not user_message.strip():
            return False
        
        # Filter error responses (but keep normal error replies)
        if ai_response and ai_response.startswith("❌") and ("Mode processing failed" in ai_response or "Initialization failed" in ai_response):
            return False
        
        return True
    
    def is_system_notification(self, message: BaseMessage) -> bool:
        """
        Check if message is a system notification.

        KISS Principle: Check message type directly instead of content pattern matching.
        This is more reliable and simpler than parsing square brackets.

        Args:
            message: Message object to check

        Returns:
            True if it is a system notification (SystemMessage or ToolMessage)
        """
        # System notifications are represented by SystemMessage or ToolMessage
        # KISS: Type checking is simpler and more reliable than content matching
        return isinstance(message, (SystemMessage, ToolMessage))

    def is_system_notification_legacy(self, content: str) -> bool:
        """
        DEPRECATED: Legacy method for backward compatibility.
        Check if message content is a system notification (in square brackets).

        This method is kept for backward compatibility with existing code
        that may still pass string content instead of message objects.
        New code should use is_system_notification() with BaseMessage objects.

        Args:
            content: Message content string

        Returns:
            True if content matches legacy system notification pattern
        """
        content = content.strip()
        # Legacy pattern: [Something happened...]
        return content.startswith('[') and content.endswith(']')
    
    def filter_message_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Filter message history, removing system notifications and command-related conversations.

        KISS Principle: Use simple type-based filtering instead of complex content parsing.
        SRP Principle: This method has single responsibility - filter non-conversational messages.

        Filtering Rules:
        1. Remove SystemMessage and ToolMessage (system notifications)
        2. Remove HumanMessage that are system commands
        3. Keep HumanMessage and AIMessage pairs for real conversations

        Args:
            messages: Message history list

        Returns:
            Filtered message list containing only HumanMessage and AIMessage
        """
        filtered_messages = []
        i = 0

        while i < len(messages):
            message = messages[i]

            # KISS: Skip system notifications by type checking (simpler than content matching)
            if self.is_system_notification(message):
                i += 1
                continue

            # Handle user messages
            if isinstance(message, HumanMessage):
                # Skip system commands (identified by content)
                if not self.is_system_command(message.content):
                    # Keep user message
                    filtered_messages.append(message)

                    # If the next one is an AI reply, keep it too
                    if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                        filtered_messages.append(messages[i + 1])
                        i += 1  # Skip AI message as it is already processed
                else:
                    # System command, skip user message and corresponding AI reply
                    if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                        i += 1  # Skip AI reply

            elif isinstance(message, AIMessage):
                # Standalone AI message (should not happen theoretically, but keep it)
                filtered_messages.append(message)

            i += 1

        return filtered_messages
    
    def get_conversation_summary(self, messages: List[BaseMessage], max_length: int = 200) -> str:
        """
        Get conversation summary (for debugging and display).
        
        Args:
            messages: Message list
            max_length: Maximum length
            
        Returns:
            Conversation summary
        """
        if not messages:
            return "No conversation history"
        
        # Get the last few messages
        recent_messages = messages[-4:] if len(messages) > 4 else messages
        
        summary_parts = []
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                summary_parts.append(f"User: {content}")
            elif isinstance(msg, AIMessage):
                content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                summary_parts.append(f"AI: {content}")
        
        summary = " | ".join(summary_parts)
        
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return summary