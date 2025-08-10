"""
会话存储管理器

提供会话的持久化存储和恢复功能
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class SessionStorage:
    """会话存储管理器"""
    
    def __init__(self, storage_dir: str = "data/sessions"):
        """
        初始化会话存储管理器
        
        Args:
            storage_dir: 存储目录路径
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_index_file = self.storage_dir / "sessions_index.json"
        
        # 加载会话索引
        self.sessions_index = self._load_sessions_index()
    
    def _load_sessions_index(self) -> Dict[str, Dict[str, Any]]:
        """加载会话索引"""
        try:
            if self.sessions_index_file.exists():
                with open(self.sessions_index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载会话索引失败: {e}")
        
        return {}
    
    def _save_sessions_index(self):
        """保存会话索引"""
        try:
            with open(self.sessions_index_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话索引失败: {e}")
    
    def _message_to_dict(self, message: BaseMessage) -> Dict[str, Any]:
        """将消息对象转换为字典"""
        return {
            "type": message.__class__.__name__,
            "content": message.content,
            "timestamp": datetime.now().isoformat()
        }
    
    def _dict_to_message(self, msg_dict: Dict[str, Any]) -> BaseMessage:
        """将字典转换为消息对象"""
        if msg_dict["type"] == "HumanMessage":
            return HumanMessage(content=msg_dict["content"])
        elif msg_dict["type"] == "AIMessage":
            return AIMessage(content=msg_dict["content"])
        else:
            # 默认作为HumanMessage处理
            return HumanMessage(content=msg_dict["content"])
    
    def save_session(self, session_id: str, messages: List[BaseMessage], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存会话数据
        
        Args:
            session_id: 会话ID
            messages: 消息列表
            metadata: 会话元数据
            
        Returns:
            保存是否成功
        """
        try:
            # 准备会话数据
            session_data = {
                "session_id": session_id,
                "messages": [self._message_to_dict(msg) for msg in messages],
                "message_count": len(messages),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # 如果会话已存在，保留创建时间
            if session_id in self.sessions_index:
                session_data["created_at"] = self.sessions_index[session_id]["created_at"]
            
            # 保存会话文件
            session_file = self.storage_dir / f"{session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # 更新索引
            self.sessions_index[session_id] = {
                "session_id": session_id,
                "message_count": len(messages),
                "created_at": session_data["created_at"],
                "updated_at": session_data["updated_at"],
                "file_path": str(session_file)
            }
            
            self._save_sessions_index()
            logger.info(f"会话保存成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"保存会话失败 {session_id}: {e}")
            return False
    
    def initialize_empty_session(self, session_id: str) -> bool:
        """
        初始化空会话文件
        
        Args:
            session_id: 会话ID
            
        Returns:
            初始化是否成功
        """
        try:
            # 创建空会话数据
            session_data = {
                "session_id": session_id,
                "messages": [],
                "message_count": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": {}
            }
            
            # 保存空会话文件
            session_file = self.storage_dir / f"{session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            # 更新索引
            self.sessions_index[session_id] = {
                "session_id": session_id,
                "message_count": 0,
                "created_at": session_data["created_at"],
                "updated_at": session_data["updated_at"],
                "file_path": str(session_file)
            }
            
            self._save_sessions_index()
            logger.debug(f"空会话初始化成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"初始化空会话失败 {session_id}: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[List[BaseMessage]]:
        """
        加载会话数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            消息列表，如果会话不存在返回None
        """
        try:
            session_file = self.storage_dir / f"{session_id}.json"
            
            if not session_file.exists():
                # 对于新会话，这是正常情况，不需要警告
                logger.debug(f"会话文件不存在，将创建新会话: {session_id}")
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 转换消息数据
            messages = []
            for msg_dict in session_data.get("messages", []):
                try:
                    messages.append(self._dict_to_message(msg_dict))
                except Exception as e:
                    logger.warning(f"转换消息失败: {e}")
                    continue
            
            if len(messages) > 0:
                logger.info(f"会话加载成功: {session_id}, {len(messages)} 条消息")
            else:
                logger.debug(f"空会话加载成功: {session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"加载会话失败 {session_id}: {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Returns:
            会话信息列表
        """
        # 按更新时间排序
        sessions = list(self.sessions_index.values())
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            删除是否成功
        """
        try:
            # 删除会话文件
            session_file = self.storage_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            # 从索引中移除
            if session_id in self.sessions_index:
                del self.sessions_index[session_id]
                self._save_sessions_index()
            
            logger.info(f"会话删除成功: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除会话失败 {session_id}: {e}")
            return False
    
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话是否存在
        """
        return session_id in self.sessions_index
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息字典
        """
        return self.sessions_index.get(session_id)
    
    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        清理过期会话（可选功能）
        
        Args:
            days: 保留天数
            
        Returns:
            清理的会话数量
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
            
            # 删除过期会话
            deleted_count = 0
            for session_id in sessions_to_delete:
                if self.delete_session(session_id):
                    deleted_count += 1
            
            logger.info(f"清理了 {deleted_count} 个过期会话")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理过期会话失败: {e}")
            return 0