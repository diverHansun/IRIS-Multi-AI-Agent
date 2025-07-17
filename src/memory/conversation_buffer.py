"""
对话缓冲区模块

基于LangChain 2025最佳实践实现的对话记忆管理，使用ChatMessageHistory。
"""

import logging
from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages.utils import trim_messages
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ConversationBuffer(BaseChatMessageHistory):
    """对话缓冲区管理器
    
    继承自BaseChatMessageHistory，实现LangChain标准的聊天记忆接口。
    使用trim_messages方法实现现代化的对话记忆管理。
    """
    
    def __init__(
        self,
        max_messages: int = 20,
        max_tokens: Optional[int] = 4000,
        keep_system_message: bool = True,
        include_system_in_count: bool = False
    ):
        """
        初始化对话缓冲区
        
        Args:
            max_messages: 最大保留消息数量
            max_tokens: 最大token数量限制
            keep_system_message: 是否始终保留系统消息
            include_system_in_count: 是否将系统消息计入数量限制
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.keep_system_message = keep_system_message
        self.include_system_in_count = include_system_in_count
        
        # 消息存储
        self._messages: List[BaseMessage] = []
        self._session_id: Optional[str] = None
        self._created_at = datetime.now(timezone.utc)
        
        logger.info(f"ConversationBuffer初始化 - max_messages: {max_messages}, max_tokens: {max_tokens}")
    
    def add_message(self, message: Union[BaseMessage, str, Dict[str, Any]], role: Optional[str] = None) -> None:
        """
        添加消息到缓冲区
        
        Args:
            message: 消息内容，可以是BaseMessage、字符串或字典
            role: 消息角色（当message为字符串时使用）
        """
        try:
            # 转换消息格式
            if isinstance(message, str):
                if role == "human" or role == "user":
                    msg = HumanMessage(content=message)
                elif role == "ai" or role == "assistant":
                    msg = AIMessage(content=message)
                elif role == "system":
                    msg = SystemMessage(content=message)
                else:
                    # 默认为人类消息
                    msg = HumanMessage(content=message)
            elif isinstance(message, dict):
                content = message.get("content", "")
                msg_type = message.get("type", "human")
                if msg_type == "human":
                    msg = HumanMessage(content=content)
                elif msg_type == "ai":
                    msg = AIMessage(content=content)
                elif msg_type == "system":
                    msg = SystemMessage(content=content)
                else:
                    msg = HumanMessage(content=content)
            else:
                msg = message
            
            # 添加时间戳
            if hasattr(msg, 'additional_kwargs'):
                msg.additional_kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            self._messages.append(msg)
            
            # 自动修剪消息
            self._trim_messages()
            
            logger.debug(f"添加消息: {type(msg).__name__} - {msg.content[:50]}...")
            
        except Exception as e:
            logger.error(f"添加消息失败: {e}")
            raise
    
    def add_human_message(self, content: str) -> None:
        """添加人类消息"""
        self.add_message(content, role="human")
    
    def add_ai_message(self, content: str) -> None:
        """添加AI消息"""
        self.add_message(content, role="ai")
    
    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.add_message(content, role="system")
    
    def _trim_messages(self) -> None:
        """修剪消息列表，保持在限制范围内"""
        try:
            if not self._messages:
                return
            
            # 使用LangChain的trim_messages方法
            if self.max_tokens:
                # 简单的token计数器
                def token_counter(messages):
                    return sum(len(str(msg.content)) for msg in messages)
                
                trimmed_messages = trim_messages(
                    messages=self._messages,
                    max_tokens=self.max_tokens,
                    token_counter=token_counter,
                    strategy="last",
                    start_on="human",
                    include_system=self.keep_system_message
                )
            else:
                trimmed_messages = self._messages
            
            # 如果有消息数量限制，进一步处理
            if self.max_messages > 0:
                system_msgs = [msg for msg in trimmed_messages if isinstance(msg, SystemMessage)]
                other_msgs = [msg for msg in trimmed_messages if not isinstance(msg, SystemMessage)]
                
                # 计算可保留的非系统消息数量
                max_other = self.max_messages
                if self.keep_system_message and system_msgs and not self.include_system_in_count:
                    max_other = self.max_messages
                elif self.keep_system_message and system_msgs and self.include_system_in_count:
                    max_other = self.max_messages - len(system_msgs)
                
                # 保留最新的消息
                if len(other_msgs) > max_other:
                    other_msgs = other_msgs[-max_other:]
                
                # 重新组合消息
                if self.keep_system_message and system_msgs:
                    self._messages = system_msgs + other_msgs
                else:
                    self._messages = other_msgs
            else:
                self._messages = trimmed_messages
                
            logger.debug(f"消息修剪完成，当前消息数: {len(self._messages)}")
            
        except Exception as e:
            logger.error(f"消息修剪失败: {e}")
            # 如果trim_messages失败，使用简单的截断方法
            self._simple_trim()
    
    def _simple_trim(self) -> None:
        """简单的消息截断方法（备用方案）"""
        if self.max_messages > 0 and len(self._messages) > self.max_messages:
            if self.keep_system_message:
                system_msgs = [msg for msg in self._messages if isinstance(msg, SystemMessage)]
                other_msgs = [msg for msg in self._messages if not isinstance(msg, SystemMessage)]
                
                max_other = self.max_messages - len(system_msgs) if self.include_system_in_count else self.max_messages
                if len(other_msgs) > max_other:
                    other_msgs = other_msgs[-max_other:]
                
                self._messages = system_msgs + other_msgs
            else:
                self._messages = self._messages[-self.max_messages:]
    
    @property
    def messages(self) -> List[BaseMessage]:
        """LangChain标准接口：获取所有消息"""
        return self._messages.copy()
    
    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息（兼容性方法）"""
        return self.messages
    
    def get_recent_messages(self, count: int) -> List[BaseMessage]:
        """获取最近的消息"""
        return self._messages[-count:] if count > 0 else []
    
    def clear(self) -> None:
        """清空缓冲区"""
        system_msgs = []
        if self.keep_system_message:
            system_msgs = [msg for msg in self._messages if isinstance(msg, SystemMessage)]
        
        self._messages = system_msgs
        logger.info("对话缓冲区已清空")
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要信息"""
        human_count = sum(1 for msg in self._messages if isinstance(msg, HumanMessage))
        ai_count = sum(1 for msg in self._messages if isinstance(msg, AIMessage))
        system_count = sum(1 for msg in self._messages if isinstance(msg, SystemMessage))
        
        return {
            "total_messages": len(self._messages),
            "human_messages": human_count,
            "ai_messages": ai_count,
            "system_messages": system_count,
            "session_id": self._session_id,
            "created_at": self._created_at.isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat() if self._messages else None
        }
    
    def set_session_id(self, session_id: str) -> None:
        """设置会话ID"""
        self._session_id = session_id
        logger.info(f"设置会话ID: {session_id}")
    
    def export_conversation(self) -> List[Dict[str, Any]]:
        """导出对话历史为字典格式"""
        return [
            {
                "type": type(msg).__name__.lower().replace("message", ""),
                "content": msg.content,
                "timestamp": msg.additional_kwargs.get("timestamp") if hasattr(msg, 'additional_kwargs') else None
            }
            for msg in self._messages
        ]
    
    def import_conversation(self, conversation_data: List[Dict[str, Any]]) -> None:
        """从字典格式导入对话历史"""
        self._messages = []
        for msg_data in conversation_data:
            self.add_message(msg_data["content"], role=msg_data["type"])
        
        logger.info(f"导入对话历史完成，共 {len(conversation_data)} 条消息")
    
    def __len__(self) -> int:
        """返回消息数量"""
        return len(self._messages)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ConversationBuffer(messages={len(self._messages)}, session={self._session_id})"