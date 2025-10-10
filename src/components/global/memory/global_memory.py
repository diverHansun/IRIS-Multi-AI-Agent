"""
全局记忆管理器

提供跨模式、跨LLM的统一记忆管理功能
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from ..session.message_filter import MessageFilter
from ..session.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class GlobalChatMessageHistory(BaseChatMessageHistory):
    """全局聊天消息历史实现"""
    
    def __init__(self, session_id: str, global_manager):
        """
        初始化全局聊天消息历史
        
        Args:
            session_id: 会话ID
            global_manager: 全局记忆管理器实例
        """
        self.session_id = session_id
        self.global_manager = global_manager
        self._messages: List[BaseMessage] = []
        
        # 从存储加载历史消息
        self._load_messages()
    
    def _load_messages(self):
        """从存储加载消息"""
        try:
            stored_messages = self.global_manager.storage.load_session(self.session_id)
            if stored_messages:
                self._messages = stored_messages
                logger.info(f"加载会话历史: {self.session_id}, {len(self._messages)} 条消息")
        except Exception as e:
            logger.error(f"加载会话历史失败: {e}")
            self._messages = []
    
    def add_messages(self, messages: List[BaseMessage]) -> None:
        """添加消息到历史"""
        for message in messages:
            self._messages.append(message)
        
        # 自动保存到存储
        self.global_manager._save_session_async(self.session_id, self._messages)
    
    def clear(self) -> None:
        """清除消息历史"""
        self._messages.clear()
        # 同步清除存储
        self.global_manager.storage.delete_session(self.session_id)
    
    @property
    def messages(self) -> List[BaseMessage]:
        """获取消息列表"""
        return self._messages.copy()


class GlobalMemoryManager:
    """全局记忆管理器"""
    
    def __init__(self, storage_dir: str = "data/sessions", max_messages: int = 50):
        """
        初始化全局记忆管理器
        
        Args:
            storage_dir: 存储目录
            max_messages: 最大消息数量
        """
        self.max_messages = max_messages
        self.storage = SessionStorage(storage_dir)
        self.message_filter = MessageFilter()
        
        # 内存中的会话缓存
        self._session_histories: Dict[str, GlobalChatMessageHistory] = {}
        
        logger.info(f"全局记忆管理器初始化完成，存储目录: {storage_dir}")
    
    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        获取会话历史（LangChain标准接口）
        
        Args:
            session_id: 会话ID
            
        Returns:
            聊天消息历史实例
        """
        if session_id not in self._session_histories:
            self._session_histories[session_id] = GlobalChatMessageHistory(session_id, self)
        
        return self._session_histories[session_id]
    
    def get_message_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        获取消息历史（兼容性别名）
        
        Args:
            session_id: 会话ID
            
        Returns:
            聊天消息历史实例
        """
        return self.get_session_history(session_id)
    
    def add_conversation(self, session_id: str, user_message: str, ai_response: str, 
                        current_llm_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        添加一轮对话到记忆中
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            ai_response: AI回复
            current_llm_info: 当前LLM信息（可选）
            
        Returns:
            是否成功添加
        """
        try:
            # 检查是否应该保存这个对话
            if not self.message_filter.should_save_message(user_message, ai_response):
                logger.debug(f"过滤系统命令: {user_message}")
                return False
            
            # 获取会话历史
            history = self.get_session_history(session_id)
            
            # 添加消息
            messages = [
                HumanMessage(content=user_message),
                AIMessage(content=ai_response)
            ]
            
            history.add_messages(messages)
            
            # 限制消息数量
            self._trim_messages_if_needed(session_id)
            
            logger.debug(f"添加对话到会话 {session_id}: {user_message[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"添加对话失败: {e}")
            return False
    
    def add_llm_conversation(self, session_id: str, user_message: str, ai_response: str) -> bool:
        """
        为LLM模式添加对话记忆
        
        Args:
            session_id: 会话ID
            user_message: 用户消息
            ai_response: AI回复
            
        Returns:
            是否成功添加
        """
        return self.add_conversation(session_id, user_message, ai_response)
    
    def create_runnable_with_memory(self, runnable, input_key: str = "input", 
                                  history_key: str = "chat_history"):
        """
        为Runnable对象添加记忆功能
        
        Args:
            runnable: 要包装的Runnable对象
            input_key: 输入键名
            history_key: 历史键名
            
        Returns:
            带记忆的Runnable对象
        """
        return RunnableWithMessageHistory(
            runnable,
            self.get_session_history,
            input_messages_key=input_key,
            history_messages_key=history_key
        )
    
    def migrate_session_memory(self, old_session_id: str, new_session_id: str) -> bool:
        """
        迁移会话记忆（用于切换LLM时）
        
        Args:
            old_session_id: 原会话ID
            new_session_id: 新会话ID
            
        Returns:
            迁移是否成功
        """
        try:
            # 获取原会话历史
            old_history = self.get_session_history(old_session_id)
            messages = old_history.messages
            
            if not messages:
                logger.info(f"原会话 {old_session_id} 无历史消息，无需迁移")
                return True
            
            # 创建新会话并复制消息
            new_history = self.get_session_history(new_session_id)
            new_history.add_messages(messages)
            
            logger.info(f"成功迁移 {len(messages)} 条消息从 {old_session_id} 到 {new_session_id}")
            return True
            
        except Exception as e:
            logger.error(f"迁移会话记忆失败: {e}")
            return False
    
    def add_context_marker(self, session_id: str, old_provider: str, old_model: str, 
                          new_provider: str, new_model: str, add_marker: bool = False):
        """
        添加模型切换上下文标记
        
        Args:
            session_id: 会话ID
            old_provider: 原提供商
            old_model: 原模型
            new_provider: 新提供商
            new_model: 新模型
            add_marker: 是否添加标记消息
        """
        if add_marker:
            user_msg, ai_msg = self.message_filter.create_context_marker(
                old_provider, old_model, new_provider, new_model
            )
            
            history = self.get_session_history(session_id)
            history.add_messages([user_msg, ai_msg])
            
            logger.info(f"添加模型切换标记: {old_provider}/{old_model} -> {new_provider}/{new_model}")
    
    def _trim_messages_if_needed(self, session_id: str):
        """根据需要修剪消息历史"""
        try:
            if session_id in self._session_histories:
                history = self._session_histories[session_id]
                messages = history._messages
                
                if len(messages) > self.max_messages:
                    # 保留最近的消息，但确保成对保留（用户消息+AI回复）
                    keep_count = self.max_messages
                    if keep_count % 2 == 1:
                        keep_count -= 1  # 确保偶数，保持消息对完整
                    
                    # 从后往前保留
                    history._messages = messages[-keep_count:]
                    
                    # 保存到存储
                    self._save_session_async(session_id, history._messages)
                    
                    logger.debug(f"修剪会话 {session_id} 消息历史: {len(messages)} -> {len(history._messages)}")
                    
        except Exception as e:
            logger.error(f"修剪消息历史失败: {e}")
    
    def save_session(self, session_id: str) -> bool:
        """保存会话到存储"""
        try:
            if session_id in self._session_histories:
                history = self._session_histories[session_id]
                messages = history.messages
                self.storage.save_session(session_id, messages)
                return True
            return False
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            return False
    
    def _save_session_async(self, session_id: str, messages: List[BaseMessage]):
        """异步保存会话（实际是同步实现，但接口保持一致）"""
        try:
            self.storage.save_session(session_id, messages)
        except Exception as e:
            logger.error(f"保存会话失败: {e}")
    
    def clear_session(self, session_id: str) -> bool:
        """
        清除会话记忆
        
        Args:
            session_id: 会话ID
            
        Returns:
            清除是否成功
        """
        try:
            # 清除内存缓存
            if session_id in self._session_histories:
                self._session_histories[session_id].clear()
                del self._session_histories[session_id]
            
            # 清除存储
            self.storage.delete_session(session_id)
            
            logger.info(f"清除会话记忆成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"清除会话记忆失败: {e}")
            return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        return self.storage.list_sessions()
    
    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return self.storage.session_exists(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        return self.storage.get_session_info(session_id)
    
    def get_conversation_summary(self, session_id: str) -> str:
        """获取会话摘要"""
        try:
            history = self.get_session_history(session_id)
            messages = history.messages
            return self.message_filter.get_conversation_summary(messages)
        except Exception as e:
            logger.error(f"获取会话摘要失败: {e}")
            return "获取摘要失败"
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话统计信息"""
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
                # 从存储获取信息
                session_info = self.get_session_info(session_id)
                if session_info:
                    return {
                        "session_id": session_id,
                        "total_messages": session_info.get("message_count", 0),
                        "in_memory": False
                    }
            return None
        except Exception as e:
            logger.error(f"获取会话统计失败: {e}")
            return None

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息"""
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
            logger.error(f"获取记忆统计失败: {e}")
            return {"error": str(e)}