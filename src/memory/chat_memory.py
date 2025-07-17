"""
聊天记忆模块

基于LangChain 2025最新标准实现的聊天记忆管理。
使用RunnableWithMessageHistory和ChatMessageHistory。
"""

import logging
from typing import Dict, Any, Optional, Callable
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

from .conversation_buffer import ConversationBuffer
from .memory_storage import MemoryStorage

logger = logging.getLogger(__name__)


class ChatMemoryManager:
    """聊天记忆管理器
    
    使用LangChain 2025标准模式管理聊天记忆。
    支持会话持久化和多用户管理。
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_messages: int = 20,
        max_tokens: Optional[int] = 4000,
        auto_save: bool = True
    ):
        """
        初始化聊天记忆管理器
        
        Args:
            storage_path: 存储路径
            max_messages: 最大消息数量
            max_tokens: 最大token数量
            auto_save: 是否自动保存
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.auto_save = auto_save
        
        # 存储管理器
        self.storage = MemoryStorage(storage_path, auto_save)
        
        # 会话存储 - 内存中的ChatMessageHistory实例
        self._session_store: Dict[str, BaseChatMessageHistory] = {}
        
        logger.info(f"ChatMemoryManager初始化完成")
    
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        获取会话历史记录
        
        这是RunnableWithMessageHistory要求的标准接口函数。
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话的ChatMessageHistory实例
        """
        if session_id not in self._session_store:
            # 创建新的ConversationBuffer实例
            buffer = ConversationBuffer(
                max_messages=self.max_messages,
                max_tokens=self.max_tokens
            )
            buffer.set_session_id(session_id)
            
            # 尝试从存储加载历史记录
            if self.auto_save:
                self._load_session_from_storage(session_id, buffer)
            
            self._session_store[session_id] = buffer
            logger.info(f"创建新会话历史: {session_id}")
        
        return self._session_store[session_id]
    
    def _load_session_from_storage(self, session_id: str, buffer: ConversationBuffer) -> bool:
        """从存储加载会话历史"""
        try:
            conversation_data = self.storage.load_conversation(session_id)
            if conversation_data:
                buffer.import_conversation(conversation_data)
                logger.info(f"从存储加载会话历史: {session_id} ({len(conversation_data)} 条消息)")
                return True
        except Exception as e:
            logger.warning(f"加载会话历史失败 {session_id}: {e}")
        return False
    
    def save_session(self, session_id: str) -> bool:
        """保存会话到存储"""
        if not self.auto_save:
            return False
            
        try:
            if session_id in self._session_store:
                buffer = self._session_store[session_id]
                conversation_data = buffer.export_conversation()
                metadata = {
                    "session_summary": buffer.get_conversation_summary(),
                    "saved_at": buffer._created_at.isoformat() if hasattr(buffer, '_created_at') else None
                }
                
                return self.storage.save_conversation(session_id, conversation_data, metadata)
        except Exception as e:
            logger.error(f"保存会话失败 {session_id}: {e}")
        return False
    
    def create_runnable_with_history(self, runnable) -> RunnableWithMessageHistory:
        """
        创建带记忆的Runnable
        
        Args:
            runnable: 要包装的Runnable（如Agent）
            
        Returns:
            带记忆功能的RunnableWithMessageHistory
        """
        return RunnableWithMessageHistory(
            runnable,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="output"
        )
    
    def clear_session(self, session_id: str) -> bool:
        """清空指定会话"""
        try:
            if session_id in self._session_store:
                self._session_store[session_id].clear()
                logger.info(f"会话已清空: {session_id}")
                return True
        except Exception as e:
            logger.error(f"清空会话失败 {session_id}: {e}")
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            # 从内存删除
            if session_id in self._session_store:
                del self._session_store[session_id]
            
            # 从存储删除
            if self.auto_save:
                self.storage.delete_conversation(session_id)
            
            logger.info(f"会话已删除: {session_id}")
            return True
        except Exception as e:
            logger.error(f"删除会话失败 {session_id}: {e}")
        return False
    
    def list_sessions(self) -> list:
        """列出所有会话"""
        if self.auto_save:
            return self.storage.list_conversations()
        else:
            return [{"session_id": sid, "in_memory": True} for sid in self._session_store.keys()]
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话统计信息"""
        if session_id in self._session_store:
            buffer = self._session_store[session_id]
            if hasattr(buffer, 'get_conversation_summary'):
                return buffer.get_conversation_summary()
        return None
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详细信息"""
        try:
            # 检查会话是否在内存中
            in_memory = session_id in self._session_store
            
            # 从存储获取信息
            if self.auto_save:
                metadata = self.storage.get_conversation_metadata(session_id)
                if metadata is not None:
                    # 从存储文件获取基本信息
                    conversations = self.storage.list_conversations()
                    session_info = next((c for c in conversations if c["session_id"] == session_id), None)
                    
                    if session_info:
                        info = {
                            "session_id": session_id,
                            "in_memory": in_memory,
                            "message_count": session_info["message_count"],
                            "created_at": session_info["created_at"],
                            "file_size": session_info["file_size"],
                            "metadata": metadata
                        }
                        
                        # 如果在内存中，获取实时统计
                        if in_memory:
                            buffer = self._session_store[session_id]
                            if hasattr(buffer, 'get_conversation_summary'):
                                summary = buffer.get_conversation_summary()
                                info.update({
                                    "current_message_count": summary.get("message_count", 0),
                                    "current_token_count": summary.get("token_count", 0)
                                })
                        
                        return info
            
            # 仅在内存中的会话
            elif in_memory:
                buffer = self._session_store[session_id]
                if hasattr(buffer, 'get_conversation_summary'):
                    summary = buffer.get_conversation_summary()
                    return {
                        "session_id": session_id,
                        "in_memory": True,
                        "message_count": summary.get("message_count", 0),
                        "token_count": summary.get("token_count", 0),
                        "created_at": summary.get("created_at")
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"获取会话信息失败 {session_id}: {e}")
            return None
    
    def save_all_sessions(self) -> Dict[str, bool]:
        """保存所有活跃会话"""
        results = {}
        for session_id in self._session_store.keys():
            results[session_id] = self.save_session(session_id)
        return results
    
    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """清理旧会话"""
        if self.auto_save:
            return self.storage.cleanup_old_conversations(max_age_days)
        return 0
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
        storage_stats = self.storage.get_storage_stats() if self.auto_save else {}
        
        return {
            "active_sessions": len(self._session_store),
            "sessions_in_memory": list(self._session_store.keys()),
            "storage_enabled": self.auto_save,
            "storage_stats": storage_stats,
            "config": {
                "max_messages": self.max_messages,
                "max_tokens": self.max_tokens,
                "auto_save": self.auto_save
            }
        }