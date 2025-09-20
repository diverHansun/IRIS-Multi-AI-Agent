"""
Dify 控制模块

管理 Dify 模式的初始化、配置和查询处理
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from rich.console import Console
import logging

from .client import DifyClient, DifyClientError
from .streaming import DifyStreaming
from .upload import handle_upload_command

logger = logging.getLogger(__name__)


class DifyControl:
    """Dify 控制逻辑"""
    
    def __init__(self, console: Console, config_path: str = "config/dify/config.json"):
        """
        初始化 Dify 控制器
        
        Args:
            console: Rich Console 实例
            config_path: 配置文件路径
        """
        self.console = console
        self.config_path = config_path
        self.config = None
        self.client = None
        self.streaming = None
        self.conversation_id = None  # 当前会话ID
        self.is_initialized = False
        self.uploaded_files = []  # 存储上传的文件信息
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 处理环境变量替换
            config_content = self._substitute_env_vars(config_content)
            config = json.loads(config_content)
            
            return config
            
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"配置文件格式错误: {e}")
    
    def _substitute_env_vars(self, content: str) -> str:
        """
        替换配置中的环境变量
        
        Args:
            content: 配置文件内容
            
        Returns:
            替换后的内容
        """
        import re
        
        # 匹配 ${VAR_NAME} 和 ${VAR_NAME:-default_value} 格式
        def replace_env_var(match):
            var_expr = match.group(1)
            
            if ':-' in var_expr:
                # 有默认值的情况
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                # 没有默认值的情况
                value = os.getenv(var_expr)
                if value is None:
                    raise ValueError(f"环境变量 {var_expr} 未设置且无默认值")
                return value
        
        # 替换所有环境变量
        pattern = r'\$\{([^}]+)\}'
        return re.sub(pattern, replace_env_var, content)
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置有效性
        
        Args:
            config: 配置字典
            
        Returns:
            是否有效
        """
        required_fields = ['api_key', 'base_url']
        
        for field in required_fields:
            if not config.get(field):
                self.console.print(f"[red]配置错误: 缺少必需字段 '{field}'[/red]")
                return False
        
        # 验证API密钥格式
        api_key = config['api_key']
        if not (api_key.startswith('app-') or api_key.startswith('sk-')):
            self.console.print(f"[red]配置错误: API密钥格式无效，应以 'app-' 或 'sk-' 开头[/red]")
            return False
        
        return True
    
    async def initialize(self) -> Dict[str, Any]:
        """
        初始化 Dify 客户端
        
        Returns:
            初始化结果
        """
        try:
            # 加载配置
            self.config = self._load_config()
            
            # 验证配置
            if not self._validate_config(self.config):
                return {
                    "type": "error",
                    "message": "配置验证失败"
                }
            
            # 创建客户端
            self.client = DifyClient(
                api_key=self.config['api_key'],
                base_url=self.config['base_url'],
                timeout=self.config.get('timeout', 30)
            )
            
            # 创建流式处理器，传递所有配置参数
            self.streaming = DifyStreaming(self.console)
            self.streaming.buffer_size = self.config.get('streaming_buffer_size', 200)
            self.streaming.delay_ms = self.config.get('streaming_delay_ms', 20)
            self.streaming.display_refresh_rate = self.config.get('streaming_display_refresh_rate', 15)
            self.streaming.max_content_length = self.config.get('max_content_length', 1000000)
            self.streaming.max_chunks_per_second = self.config.get('max_chunks_per_second', 50)
            
            # 测试连接
            await self._test_connection()
            
            self.is_initialized = True
            
            return {
                "type": "success",
                "message": "Dify 客户端初始化成功"
            }
            
        except FileNotFoundError as e:
            return {
                "type": "error",
                "message": f"配置文件错误: {e}"
            }
        except ValueError as e:
            return {
                "type": "error",
                "message": f"环境变量错误: {e}"
            }
        except Exception as e:
            logger.error(f"Dify 初始化失败: {e}")
            return {
                "type": "error",
                "message": f"初始化失败: {e}"
            }
    
    async def _test_connection(self):
        """
        测试与 Dify 的连接
        
        Raises:
            DifyClientError: 连接失败时抛出
        """
        try:
            # 发送一个简单的测试请求
            async for _ in self.client.chat_message(
                query="hello", 
                user_id="test_user", 
                streaming=False
            ):
                break  # 只要能收到响应就说明连接正常
                    
        except Exception as e:
            raise DifyClientError(f"连接测试失败: {e}")
    
    async def handle_query(self, query: str, user_id: str) -> Dict[str, Any]:
        """
        处理用户查询
        
        Args:
            query: 用户查询
            user_id: 用户ID
            
        Returns:
            处理结果
        """
        if not self.is_initialized:
            return {
                "type": "error",
                "message": "Dify 客户端未初始化，请先执行 'switch dify'"
            }
        
        try:
            # 准备当前查询使用的文件列表（一次性使用）
            current_files = self.uploaded_files.copy() if self.uploaded_files else None
            
            # 发送查询并处理流式响应
            stream = self.client.chat_message(
                query=query,
                user_id=user_id,
                streaming=True,
                conversation_id=self.conversation_id,
                files=current_files
            )
            
            # 清空上传的文件列表（实现一次性使用）
            if self.uploaded_files:
                file_count = len(self.uploaded_files)
                self.uploaded_files.clear()
                self.console.print(f"[dim]已使用 {file_count} 个文件，文件列表已清空[/dim]")
            
            # 显示流式响应
            new_conversation_id = await self.streaming.display_stream(stream)
            
            # 更新会话ID
            if new_conversation_id:
                self.conversation_id = new_conversation_id
            
            return {
                "type": "success",
                "conversation_id": self.conversation_id
            }
            
        except DifyClientError as e:
            await self.streaming.display_error(str(e))
            return {
                "type": "error",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            await self.streaming.display_error(f"查询处理失败: {e}")
            return {
                "type": "error",
                "message": f"查询处理失败: {e}"
            }
    
    async def handle_upload(self, query: str, ctx) -> Dict[str, Any]:
        """
        处理文件上传命令
        
        Args:
            query: 上传命令
            ctx: 应用上下文
            
        Returns:
            处理结果
        """
        if not self.is_initialized:
            return {
                "type": "error",
                "message": "Dify 客户端未初始化，请先执行 'switch dify'"
            }
        
        result = await handle_upload_command(
            ctx=ctx,
            query=query,
            client=self.client,
            console=self.console,
            config=self.config
        )
        
        # 如果上传成功，将文件信息添加到列表中
        if result.get("type") == "success" and "file_info" in result:
            file_info = result["file_info"]
            
            # 根据文件扩展名判断类型
            file_extension = file_info.get('extension', '').lower()
            file_type = "image" if file_extension in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'] else "document"
            
            # 添加文件到上传列表，格式为 Dify 要求的格式
            self.uploaded_files.append({
                "type": file_type,
                "transfer_method": "remote_url",
                "upload_file_id": file_info.get("id")
            })
            self.console.print(f"[dim]文件已添加到对话上下文: {file_info.get('name', 'Unknown')} (类型: {file_type}) - 将在下次对话中使用[/dim]")
        
        return result
    
    async def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态信息
        
        Returns:
            状态信息字典
        """
        return {
            "initialized": self.is_initialized,
            "conversation_id": self.conversation_id,
            "config_loaded": self.config is not None,
            "client_ready": self.client is not None
        }
    
    async def get_detailed_info(self) -> Dict[str, Any]:
        """
        获取详细的 Dify 状态信息，用于 info 命令
        
        Returns:
            详细的 Dify 状态信息
        """
        status = await self.get_status()
        
        # 构建详细信息
        info = {
            "provider": "Dify",
            "model": "Cloud AI",
            "initialized": status["initialized"],
            "base_url": self.config.get("base_url", "N/A") if self.config else "N/A",
            "api_key_prefix": self.config["api_key"][:10] + "..." if self.config and self.config.get("api_key") else "N/A",
            "conversation_id": status["conversation_id"],
            "uploaded_files_count": len(self.uploaded_files),
            "uploaded_files": [
                {
                    "type": file.get("type", "unknown"),
                    "file_id": file.get("upload_file_id", "unknown")
                }
                for file in self.uploaded_files
            ],
            "timeout": self.config.get("timeout", 30) if self.config else 30,
            "supported_file_types": self.config.get("supported_file_types", []) if self.config else [],
            "max_file_size_mb": (self.config.get("max_file_size", 10485760) / 1024 / 1024) if self.config else 10
        }
        
        return info
    
    async def reset_conversation(self):
        """重置当前会话"""
        self.conversation_id = None
        self.uploaded_files = []  # 同时清空文件列表
        await self.streaming.display_info("会话已重置，文件列表已清空")
    
    async def clear_files(self):
        """清空文件列表"""
        if self.uploaded_files:
            file_count = len(self.uploaded_files)
            self.uploaded_files = []
            self.console.print(f"[yellow]已清空 {file_count} 个待发送文件[/yellow]")
        else:
            self.console.print("[dim]文件列表已为空[/dim]")
    
    async def list_files(self):
        """列出当前待发送的文件"""
        if not self.uploaded_files:
            self.console.print("[dim]当前没有待发送的文件[/dim]")
            return
        
        self.console.print(f"[blue]当前有 {len(self.uploaded_files)} 个文件待发送：[/blue]")
        for i, file_info in enumerate(self.uploaded_files, 1):
            file_type = file_info.get("type", "unknown")
            file_id = file_info.get("upload_file_id", "unknown")
            self.console.print(f"  {i}. 类型: {file_type} | ID: {file_id}")
        self.console.print("[dim]这些文件将在下次对话中一次性使用[/dim]")
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.client:
                await self.client.close()
                self.client = None
        except Exception as e:
            logger.warning(f"清理 Dify 客户端时出错: {e}")
        finally:
            self.is_initialized = False
            self.conversation_id = None
            self.uploaded_files = []
            self.streaming = None


async def init_dify_client(ctx) -> Dict[str, Any]:
    """
    初始化 Dify 客户端的便捷函数
    
    Args:
        ctx: 应用上下文
        
    Returns:
        初始化结果
    """
    control = DifyControl(ctx.console)
    result = await control.initialize()
    
    if result["type"] == "success":
        # 保存控制器实例到上下文
        ctx.dify_control = control
    
    return result


async def handle_dify_query(ctx, query: str) -> Dict[str, Any]:
    """
    处理 Dify 查询的便捷函数
    
    Args:
        ctx: 应用上下文
        query: 用户查询
        
    Returns:
        处理结果
    """
    if not hasattr(ctx, 'dify_control') or not ctx.dify_control:
        return {
            "type": "error",
            "message": "Dify 客户端未初始化"
        }
    
    user_id = getattr(ctx, 'session_id', 'default_user')
    return await ctx.dify_control.handle_query(query, user_id)


async def handle_dify_upload(ctx, query: str) -> Dict[str, Any]:
    """
    处理 Dify 上传的便捷函数
    
    Args:
        ctx: 应用上下文
        query: 上传命令
        
    Returns:
        处理结果
    """
    if not hasattr(ctx, 'dify_control') or not ctx.dify_control:
        return {
            "type": "error",
            "message": "Dify 客户端未初始化"
        }
    
    return await ctx.dify_control.handle_upload(query, ctx)
