"""
记忆存储模块

提供持久化存储功能，支持JSON文件存储和内存存储。
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryStorage:
    """记忆存储管理器
    
    提供对话记忆的持久化存储功能。
    """
    
    def __init__(self, storage_path: Optional[str] = None, auto_save: bool = True):
        """
        初始化存储管理器
        
        Args:
            storage_path: 存储文件路径，默认为项目根目录下的.memory文件夹
            auto_save: 是否自动保存
        """
        self.auto_save = auto_save
        
        # 设置存储路径
        if storage_path is None:
            # 使用项目根目录下的.memory文件夹
            project_root = Path(__file__).parent.parent.parent
            self.storage_dir = project_root / ".memory"
        else:
            self.storage_dir = Path(storage_path)
        
        # 创建存储目录
        self.storage_dir.mkdir(exist_ok=True)
        
        # 内存缓存
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"MemoryStorage初始化 - 存储路径: {self.storage_dir}")
    
    def save_conversation(self, session_id: str, conversation_data: List[Dict[str, Any]], 
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存对话到存储
        
        Args:
            session_id: 会话ID
            conversation_data: 对话数据
            metadata: 元数据
            
        Returns:
            是否保存成功
        """
        try:
            # 准备保存数据
            save_data = {
                "session_id": session_id,
                "conversation": conversation_data,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message_count": len(conversation_data)
            }
            
            # 保存到文件
            file_path = self.storage_dir / f"{session_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 更新缓存
            self._cache[session_id] = save_data
            
            logger.info(f"对话已保存: {session_id} ({len(conversation_data)} 条消息)")
            return True
            
        except Exception as e:
            logger.error(f"保存对话失败 {session_id}: {e}")
            return False
    
    def load_conversation(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        加载对话记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            对话数据，如果不存在返回None
        """
        try:
            # 先检查缓存
            if session_id in self._cache:
                return self._cache[session_id]["conversation"]
            
            # 从文件加载
            file_path = self.storage_dir / f"{session_id}.json"
            if not file_path.exists():
                logger.debug(f"对话文件不存在: {session_id}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新缓存
            self._cache[session_id] = data
            
            logger.info(f"对话已加载: {session_id} ({data['message_count']} 条消息)")
            return data["conversation"]
            
        except Exception as e:
            logger.error(f"加载对话失败 {session_id}: {e}")
            return None
    
    def delete_conversation(self, session_id: str) -> bool:
        """
        删除对话记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        try:
            # 从缓存删除
            if session_id in self._cache:
                del self._cache[session_id]
            
            # 删除文件
            file_path = self.storage_dir / f"{session_id}.json"
            if file_path.exists():
                file_path.unlink()
                logger.info(f"对话已删除: {session_id}")
                return True
            else:
                logger.warning(f"对话文件不存在: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除对话失败 {session_id}: {e}")
            return False
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        列出所有对话记录的摘要信息
        
        Returns:
            对话摘要列表
        """
        conversations = []
        
        try:
            # 扫描存储目录
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    session_id = file_path.stem
                    
                    # 检查缓存
                    if session_id in self._cache:
                        data = self._cache[session_id]
                    else:
                        # 从文件加载基本信息
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    
                    # 添加摘要信息
                    conversations.append({
                        "session_id": session_id,
                        "message_count": data.get("message_count", 0),
                        "created_at": data.get("created_at"),
                        "metadata": data.get("metadata", {}),
                        "file_size": file_path.stat().st_size
                    })
                    
                except Exception as e:
                    logger.warning(f"读取对话文件失败 {file_path}: {e}")
                    continue
            
            # 按创建时间排序
            conversations.sort(key=lambda x: x["created_at"] or "", reverse=True)
            
            logger.info(f"找到 {len(conversations)} 个对话记录")
            return conversations
            
        except Exception as e:
            logger.error(f"列出对话记录失败: {e}")
            return []
    
    def get_conversation_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取对话元数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            元数据字典
        """
        try:
            # 先检查缓存
            if session_id in self._cache:
                return self._cache[session_id].get("metadata", {})
            
            # 从文件加载
            file_path = self.storage_dir / f"{session_id}.json"
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data.get("metadata", {})
            
        except Exception as e:
            logger.error(f"获取元数据失败 {session_id}: {e}")
            return None
    
    def update_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """
        更新对话元数据
        
        Args:
            session_id: 会话ID
            metadata: 新的元数据
            
        Returns:
            是否更新成功
        """
        try:
            # 加载现有数据
            file_path = self.storage_dir / f"{session_id}.json"
            if not file_path.exists():
                logger.warning(f"对话不存在: {session_id}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 更新元数据
            data["metadata"].update(metadata)
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # 保存回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 更新缓存
            if session_id in self._cache:
                self._cache[session_id] = data
            
            logger.info(f"元数据已更新: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新元数据失败 {session_id}: {e}")
            return False
    
    def cleanup_old_conversations(self, max_age_days: int = 30) -> int:
        """
        清理旧的对话记录
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            清理的对话数量
        """
        cleaned_count = 0
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_days * 24 * 3600)
        
        try:
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    # 检查文件修改时间
                    if file_path.stat().st_mtime < cutoff_time:
                        session_id = file_path.stem
                        
                        # 删除文件和缓存
                        file_path.unlink()
                        if session_id in self._cache:
                            del self._cache[session_id]
                        
                        cleaned_count += 1
                        logger.debug(f"清理旧对话: {session_id}")
                
                except Exception as e:
                    logger.warning(f"清理文件失败 {file_path}: {e}")
                    continue
            
            if cleaned_count > 0:
                logger.info(f"清理完成，删除了 {cleaned_count} 个旧对话")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理操作失败: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            存储统计字典
        """
        try:
            conversations = self.list_conversations()
            total_size = sum(conv["file_size"] for conv in conversations)
            total_messages = sum(conv["message_count"] for conv in conversations)
            
            return {
                "conversation_count": len(conversations),
                "total_messages": total_messages,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "storage_path": str(self.storage_dir),
                "cache_size": len(self._cache)
            }
            
        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
            return {}