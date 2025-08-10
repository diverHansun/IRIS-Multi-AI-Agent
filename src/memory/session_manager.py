"""
会话管理器

提供会话的创建、切换、恢复等高级管理功能
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
from rich.console import Console

from .global_memory import GlobalMemoryManager

console = Console()

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器，提供高级会话管理功能"""
    
    def __init__(self, memory_manager: GlobalMemoryManager):
        """
        初始化会话管理器
        
        Args:
            memory_manager: 全局记忆管理器实例
        """
        self.memory_manager = memory_manager
        self.current_session_id: Optional[str] = None
        
        logger.info("会话管理器初始化完成")
    
    def create_new_session(self, user_prefix: str = "user") -> str:
        """
        创建新的会话
        
        Args:
            user_prefix: 用户前缀
            
        Returns:
            新的会话ID
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        session_id = f"{user_prefix}_{timestamp}_{unique_id}"
        
        self.current_session_id = session_id
        
        # 立即在存储中创建空会话文件，避免后续加载时的警告
        self.memory_manager.storage.initialize_empty_session(session_id)
        
        console.print(f"[dim]已创建新会话: {session_id}[/]")
        
        return session_id
    
    def get_or_create_default_session(self) -> str:
        """
        获取或创建默认会话
        
        Returns:
            会话ID
        """
        if not self.current_session_id:
            # 尝试恢复最近的会话
            recent_session = self.get_most_recent_session()
            if recent_session:
                self.current_session_id = recent_session["session_id"]
                console.print(f"[dim]已加载最近会话: {self.current_session_id}[/]")
            else:
                # 创建新会话
                self.current_session_id = self.create_new_session()
            
        
        return self.current_session_id
    
    def switch_to_session(self, session_id: str) -> bool:
        """
        切换到指定会话
        
        Args:
            session_id: 目标会话ID
            
        Returns:
            切换是否成功
        """
        if not self.memory_manager.session_exists(session_id):
            logger.error(f"会话不存在: {session_id}")
            return False
        
        old_session = self.current_session_id
        self.current_session_id = session_id
        
        logger.info(f"切换会话: {old_session} -> {session_id}")
        return True
    
    def get_most_recent_session(self) -> Optional[Dict[str, Any]]:
        """
        获取最近的会话
        
        Returns:
            最近的会话信息，如果没有返回None
        """
        sessions = self.memory_manager.list_sessions()
        if sessions:
            return sessions[0]  # 已按更新时间排序
        return None
    
    def migrate_to_new_session_for_llm_switch(self, old_provider: str, old_model: str, 
                                            new_provider: str, new_model: str, 
                                            preserve_history: bool = True) -> str:
        """
        为LLM切换创建新会话并迁移历史（如果需要）
        
        Args:
            old_provider: 原LLM提供商
            old_model: 原模型
            new_provider: 新LLM提供商
            new_model: 新模型
            preserve_history: 是否保留历史对话
            
        Returns:
            新的会话ID
        """
        old_session_id = self.current_session_id
        
        if preserve_history and old_session_id:
            # 使用相同的会话ID，保持对话连续性
            logger.info(f"LLM切换保持会话连续性: {old_provider}/{old_model} -> {new_provider}/{new_model}")
            
            # 可选：添加切换标记
            # self.memory_manager.add_context_marker(
            #     old_session_id, old_provider, old_model, new_provider, new_model, add_marker=False
            # )
            
            return old_session_id
        else:
            # 创建新会话
            new_session_id = self.create_new_session()
            
            if preserve_history and old_session_id:
                # 迁移历史记忆
                self.memory_manager.migrate_session_memory(old_session_id, new_session_id)
            
            logger.info(f"LLM切换创建新会话: {new_session_id}")
            return new_session_id
    
    def get_current_session_summary(self) -> str:
        """
        获取当前会话摘要
        
        Returns:
            会话摘要
        """
        if not self.current_session_id:
            return "当前无活动会话"
        
        return self.memory_manager.get_conversation_summary(self.current_session_id)
    
    def clear_current_session(self) -> bool:
        """
        清除当前会话
        
        Returns:
            清除是否成功
        """
        if not self.current_session_id:
            return False
        
        success = self.memory_manager.clear_session(self.current_session_id)
        if success:
            logger.info(f"清除当前会话: {self.current_session_id}")
        
        return success
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        获取会话统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.memory_manager.get_memory_stats()
        stats.update({
            "current_session_id": self.current_session_id,
            "current_session_summary": self.get_current_session_summary() if self.current_session_id else None
        })
        
        return stats
    
    def validate_session_id(self, session_id: str) -> bool:
        """
        验证会话ID格式
        
        Args:
            session_id: 要验证的会话ID
            
        Returns:
            是否有效
        """
        if not session_id or not isinstance(session_id, str):
            return False
        
        # 基本格式检查
        parts = session_id.split('_')
        if len(parts) < 3:
            return False
        
        return True
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        清理旧会话
        
        Args:
            days: 保留天数
            
        Returns:
            清理的会话数量
        """
        try:
            return self.memory_manager.storage.cleanup_old_sessions(days)
        except Exception as e:
            logger.error(f"清理旧会话失败: {e}")
            return 0