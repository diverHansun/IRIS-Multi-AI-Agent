"""
Dify 控制模块

管理 Dify 模式的初始化、配置和查询处理
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional,List
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
    
    async def initialize(self, force_reinit: bool = False) -> Dict[str, Any]:
        """
        初始化 Dify 客户端
        
        Args:
            force_reinit: 是否强制重新初始化（即使已经初始化过）
        
        Returns:
            初始化结果
        """
        try:
            # 如果已经初始化且不强制重新初始化，直接返回成功
            if self.is_initialized and not force_reinit:
                return {
                    "type": "success",
                    "message": "Dify 客户端已经初始化"
                }
            
            # 如果已初始化且需要重新初始化，先清理现有连接
            if self.is_initialized and force_reinit:
                await self.cleanup()
            
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
            # 过滤掉本地显示字段（以下划线开头的字段）
            current_files = None
            if self.uploaded_files:
                current_files = [
                    {k: v for k, v in f.items() if not k.startswith('_')}
                    for f in self.uploaded_files
                ]

                # 调试输出：显示实际发送的files参数
                logger.debug(f"发送的files参数: {current_files}")
                self.console.print(f"[dim]调试信息 - 发送files参数: {current_files}[/dim]")

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
        if result.get("type") == "success" and "uploaded_files" in result:
            uploaded_files = result["uploaded_files"]

            for file_result in uploaded_files:
                file_info = file_result.get('raw_response', {})

                # 根据文件扩展名或返回类型判断类型
                file_extension = file_info.get('extension', '').lower()
                # 确保扩展名以点号开头
                if file_extension and not file_extension.startswith('.'):
                    file_extension = '.' + file_extension

                file_type = file_result.get('type', 'document')

                if not file_type or file_type == 'file':
                    file_type = "image" if file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'] else "document"

                # 添加文件到上传列表，格式为 Dify 要求的格式，并保存文件名用于显示
                self.uploaded_files.append({
                    "type": file_type,
                    "transfer_method": "local_file",
                    "upload_file_id": file_info.get("id") or file_result.get('file_id'),
                    "_filename": file_result.get('filename', 'Unknown'),  # 本地显示字段
                    "_size": file_result.get('size', 0)  # 本地显示字段
                })

            # 显示添加结果
            if len(uploaded_files) == 1:
                file_name = uploaded_files[0].get('filename', 'Unknown')
                file_type = self.uploaded_files[-1]['type']
                self.console.print(f"[dim]文件已添加到对话上下文: {file_name} (类型: {file_type}) - 将在下次对话中使用[/dim]")
            else:
                self.console.print(f"[dim]{len(uploaded_files)} 个文件已添加到对话上下文 - 将在下次对话中使用[/dim]")

            # 显示当前待发送文件总数
            self.console.print(f"[blue]当前共有 {len(self.uploaded_files)} 个文件待发送[/blue]")

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

        total_size = 0
        for i, file_info in enumerate(self.uploaded_files, 1):
            file_type = file_info.get("type", "unknown")
            file_id = file_info.get("upload_file_id", "unknown")
            filename = file_info.get("_filename", "Unknown")
            file_size = file_info.get("_size", 0)
            total_size += file_size

            # 格式化文件大小
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f}MB"
            elif file_size > 1024:
                size_str = f"{file_size / 1024:.1f}KB"
            else:
                size_str = f"{file_size}B"

            # 使用不同颜色区分文件类型
            type_color = "cyan" if file_type == "image" else "yellow"
            self.console.print(f"  [{i}] [{type_color}]{file_type:8}[/{type_color}] {filename} ({size_str})")
            self.console.print(f"      [dim]ID: {file_id}[/dim]")

        # 显示总大小
        if total_size > 1024 * 1024:
            total_size_str = f"{total_size / (1024 * 1024):.1f}MB"
        elif total_size > 1024:
            total_size_str = f"{total_size / 1024:.1f}KB"
        else:
            total_size_str = f"{total_size}B"

        self.console.print(f"[dim]总大小: {total_size_str}[/dim]")
        self.console.print("[dim]提示: 这些文件将在下次对话中一次性使用，使用后自动清空[/dim]")
        self.console.print("[dim]提示: 使用 '/files remove <序号>' 可以移除指定文件[/dim]")

    async def remove_file(self, index: int) -> bool:
        """
        从待发送列表中移除指定序号的文件

        Args:
            index: 文件序号（从1开始）

        Returns:
            是否成功移除
        """
        if not self.uploaded_files:
            self.console.print("[yellow]当前没有待发送的文件[/yellow]")
            return False

        if index < 1 or index > len(self.uploaded_files):
            self.console.print(f"[red]无效的序号: {index}，有效范围: 1-{len(self.uploaded_files)}[/red]")
            return False

        # 移除文件（序号从1开始，索引从0开始）
        removed_file = self.uploaded_files.pop(index - 1)
        filename = removed_file.get("_filename", "Unknown")
        self.console.print(f"[green]已移除文件: {filename}[/green]")
        self.console.print(f"[dim]剩余 {len(self.uploaded_files)} 个文件待发送[/dim]")
        return True

    async def remove_files_by_indices(self, indices: List[int]) -> Dict[str, Any]:
        """
        批量移除多个文件

        Args:
            indices: 文件序号列表（从1开始）

        Returns:
            移除结果
        """
        if not self.uploaded_files:
            self.console.print("[yellow]当前没有待发送的文件[/yellow]")
            return {"removed": 0, "failed": 0}

        # 按降序排序，避免删除时索引错位
        sorted_indices = sorted(set(indices), reverse=True)

        removed_count = 0
        failed_count = 0

        for index in sorted_indices:
            if 1 <= index <= len(self.uploaded_files):
                removed_file = self.uploaded_files.pop(index - 1)
                filename = removed_file.get("_filename", "Unknown")
                self.console.print(f"[green] 已移除: {filename}[/green]")
                removed_count += 1
            else:
                self.console.print(f"[yellow] 无效序号: {index}[/yellow]")
                failed_count += 1

        self.console.print(f"[dim]成功移除 {removed_count} 个文件，剩余 {len(self.uploaded_files)} 个文件待发送[/dim]")

        return {"removed": removed_count, "failed": failed_count}
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 关闭客户端连接
            if self.client:
                try:
                    await self.client.close()
                    self.client = None
                    logger.debug("Dify 客户端连接已关闭")
                except Exception as e:
                    logger.warning(f"关闭 Dify 客户端连接时出错: {e}")
            
            # 重置流式处理器
            if self.streaming:
                self.streaming = None
                
        except Exception as e:
            logger.warning(f"清理 Dify 资源时出错: {e}")
        finally:
            # 重置所有状态
            self.is_initialized = False
            self.conversation_id = None
            self.uploaded_files = []
            self.config = None


async def init_dify_client(ctx, force_reinit: bool = False) -> Dict[str, Any]:
    """
    初始化 Dify 客户端的便捷函数
    
    Args:
        ctx: 应用上下文
        force_reinit: 是否强制重新初始化
        
    Returns:
        初始化结果
    """
    # 如果已存在控制器且不强制重新初始化，直接使用现有实例
    if ctx.dify_control and ctx.dify_control.is_initialized and not force_reinit:
        return {
            "type": "success",
            "message": "使用现有的 Dify 客户端连接"
        }
    
    # 如果需要强制重新初始化，先清理现有连接
    if ctx.dify_control and force_reinit:
        await ctx.dify_control.cleanup()
        ctx.dify_control = None
    
    # 创建新的控制器实例
    control = DifyControl(ctx.console)
    result = await control.initialize(force_reinit=force_reinit)
    
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
