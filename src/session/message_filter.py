"""
消息过滤器

过滤系统命令，只保留真实的用户对话和AI回复
"""

import re
from typing import List, Dict, Any, Tuple
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class MessageFilter:
    """消息过滤器，用于过滤系统命令和保留对话内容"""
    
    # 需要过滤的系统命令
    SYSTEM_COMMANDS = {
        'help', '帮助', 'info', '信息', 
        'llms', 'llm', '模型列表',
        'clear', '清除记忆', '重置',
        'sessions', '会话列表', 'ls',
        'exit', 'quit', '退出'
    }
    
    # 命令前缀模式
    COMMAND_PREFIXES = [
        r'^switch\s+',      # switch openai gpt-4o
        r'^mode\s+',        # mode llm/agent
        r'^stream\s+',      # stream on/off
        r'^restore\s+',     # restore session_id
    ]
    
    def __init__(self):
        """初始化消息过滤器"""
        self.command_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.COMMAND_PREFIXES]
    
    def is_system_command(self, message: str) -> bool:
        """
        判断消息是否为系统命令
        
        Args:
            message: 用户消息内容
            
        Returns:
            True如果是系统命令，False如果是普通对话
        """
        message = message.strip().lower()
        
        # 检查精确匹配的系统命令
        if message in self.SYSTEM_COMMANDS:
            return True
        
        # 检查命令前缀模式
        for pattern in self.command_patterns:
            if pattern.match(message):
                return True
        
        return False
    
    def should_save_message(self, user_message: str, ai_response: str = "") -> bool:
        """
        判断对话是否应该保存到记忆中
        
        Args:
            user_message: 用户消息
            ai_response: AI回复
            
        Returns:
            True如果应该保存，False如果应该过滤
        """
        # 过滤系统命令
        if self.is_system_command(user_message):
            return False
        
        # 过滤空消息
        if not user_message.strip():
            return False
        
        # 过滤错误响应（但保留正常的错误回复）
        if ai_response and ai_response.startswith("❌") and ("模式处理失败" in ai_response or "初始化失败" in ai_response):
            return False
        
        return True
    
    def filter_message_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        过滤消息历史，移除系统命令相关的对话
        
        Args:
            messages: 消息历史列表
            
        Returns:
            过滤后的消息列表
        """
        filtered_messages = []
        i = 0
        
        while i < len(messages):
            message = messages[i]
            
            # 如果是用户消息，检查是否为系统命令
            if isinstance(message, HumanMessage):
                if not self.is_system_command(message.content):
                    # 保留用户消息
                    filtered_messages.append(message)
                    
                    # 如果下一条是AI回复，也保留
                    if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                        filtered_messages.append(messages[i + 1])
                        i += 1  # 跳过AI消息，因为已经处理
                else:
                    # 系统命令，跳过用户消息和对应的AI回复
                    if i + 1 < len(messages) and isinstance(messages[i + 1], AIMessage):
                        i += 1  # 跳过AI回复
            elif isinstance(message, AIMessage):
                # 单独的AI消息（理论上不应该出现）
                filtered_messages.append(message)
            
            i += 1
        
        return filtered_messages
    
    def create_context_marker(self, old_provider: str, old_model: str, new_provider: str, new_model: str) -> Tuple[HumanMessage, AIMessage]:
        """
        创建模型切换的上下文标记（可选功能）
        
        Args:
            old_provider: 原提供商
            old_model: 原模型
            new_provider: 新提供商  
            new_model: 新模型
            
        Returns:
            标记消息对（用户消息，AI回复）
        """
        user_msg = HumanMessage(content=f"[系统] 模型已从 {old_provider}/{old_model} 切换到 {new_provider}/{new_model}")
        ai_msg = AIMessage(content=f"好的，我现在使用 {new_provider}/{new_model} 为您服务。我记住了之前的对话内容。")
        
        return user_msg, ai_msg
    
    def get_conversation_summary(self, messages: List[BaseMessage], max_length: int = 200) -> str:
        """
        获取对话摘要（用于调试和展示）
        
        Args:
            messages: 消息列表
            max_length: 最大长度
            
        Returns:
            对话摘要
        """
        if not messages:
            return "暂无对话历史"
        
        # 获取最后几条对话
        recent_messages = messages[-4:] if len(messages) > 4 else messages
        
        summary_parts = []
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                summary_parts.append(f"用户: {content}")
            elif isinstance(msg, AIMessage):
                content = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                summary_parts.append(f"AI: {content}")
        
        summary = " | ".join(summary_parts)
        
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        
        return summary