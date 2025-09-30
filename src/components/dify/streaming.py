"""
Dify 流式输出处理模块

处理 Dify API 的流式响应和输出显示
"""

import json
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator
from rich.console import Console
from rich.text import Text
from rich.status import Status
from rich.panel import Panel
import logging

logger = logging.getLogger(__name__)


class DifyStreaming:
    """Dify 流式输出处理"""
    
    def __init__(self, console: Console):
        """
        初始化流式输出处理器
        
        Args:
            console: Rich Console 实例
        """
        self.console = console
        self._current_message_id = None
        self._current_conversation_id = None
        
        # 性能监控和控制参数
        self.buffer_size = 200
        self.delay_ms = 20
        self.display_refresh_rate = 15
        self.max_content_length = 1000000
        self.max_chunks_per_second = 50
        
        # 性能统计
        self._start_time = None
        self._chunk_count = 0
        self._total_chars = 0
        self._last_chunk_time = 0
    
    async def _apply_rate_limit(self) -> None:
        """应用速率限制，防止处理过于频繁"""
        current_time = time.time()
        
        # 计算当前处理速率
        if self._start_time and current_time > self._start_time:
            elapsed = current_time - self._start_time
            chunks_per_second = self._chunk_count / elapsed
            
            # 如果速率过高，添加延迟
            if chunks_per_second > self.max_chunks_per_second:
                delay = max(0, self.delay_ms / 1000.0)
                await asyncio.sleep(delay)
        
        # 更新最后处理时间
        self._last_chunk_time = current_time
    
    def _update_statistics(self, content: str) -> None:
        """更新性能统计"""
        self._chunk_count += 1
        self._total_chars += len(content)
        
        if self._start_time is None:
            self._start_time = time.time()
    
    def _get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        if not self._start_time:
            return {}
        
        elapsed = time.time() - self._start_time
        chars_per_second = self._total_chars / elapsed if elapsed > 0 else 0
        chunks_per_second = self._chunk_count / elapsed if elapsed > 0 else 0
        
        return {
            "elapsed_time": elapsed,
            "total_chunks": self._chunk_count,
            "total_chars": self._total_chars,
            "chars_per_second": chars_per_second,
            "chunks_per_second": chunks_per_second
        }
    
    def parse_stream_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析流式数据
        
        Args:
            data: 原始流式数据
            
        Returns:
            解析后的数据，如果无效则返回None
        """
        try:
            event = data.get('event')
            
            if event == 'message':
                # 消息事件，包含部分回复内容
                return {
                    'type': 'message',
                    'content': data.get('answer', ''),
                    'message_id': data.get('message_id'),
                    'conversation_id': data.get('conversation_id')
                }
            
            elif event == 'message_end':
                # 消息结束事件，包含完整回复
                return {
                    'type': 'message_end',
                    'content': data.get('answer', ''),
                    'message_id': data.get('message_id'),
                    'conversation_id': data.get('conversation_id'),
                    'metadata': data.get('metadata', {})
                }
            
            elif event == 'error':
                # 错误事件
                return {
                    'type': 'error',
                    'error': data.get('error', 'Unknown error'),
                    'message': data.get('message', '')
                }
            
            elif event == 'message_file':
                # 文件消息事件
                return {
                    'type': 'file',
                    'file_id': data.get('file_id'),
                    'filename': data.get('filename'),
                    'url': data.get('url')
                }
            
            else:
                # 其他事件类型
                return {
                    'type': 'other',
                    'event': event,
                    'data': data
                }
                
        except Exception as e:
            logger.warning(f"解析流式数据失败: {e}, data: {data}")
            return None
    
    async def display_stream(
        self, 
        stream_generator: AsyncGenerator[Dict[str, Any], None],
        show_typing: bool = True
    ) -> Optional[str]:
        """
        显示流式输出
        
        Args:
            stream_generator: 流式数据生成器
            show_typing: 是否显示打字效果
            
        Returns:
            最终的会话ID，用于后续请求
        """
        content_buffer = []
        conversation_id = None
        message_id = None
        
        try:
            # 显示等待状态
            if show_typing:
                status = Status("正在思考...", console=self.console, spinner="dots")
                status.start()
            
            first_content_received = False
            content_buffer = []
            display_buffer = []  # 显示缓冲，减少实时输出频率
            
            chunk_count = 0
            max_chunks = 10000  # 设置最大处理块数，防止无限循环
            buffer_size = getattr(self, 'buffer_size', 200)  # 从配置获取缓冲大小，默认200
            
            # 重置性能统计
            self._start_time = None
            self._chunk_count = 0
            self._total_chars = 0
            
            async for raw_data in stream_generator:
                chunk_count += 1
                
                # 防止处理过多数据块导致内存问题
                if chunk_count > max_chunks:
                    logger.warning(f"流式数据块数量超过限制: {max_chunks}")
                    self.console.print(f"\n[yellow]⚠️ 响应内容过长，已截断处理[/yellow]")
                    break
                
                parsed_data = self.parse_stream_data(raw_data)
                
                if not parsed_data:
                    continue
                
                data_type = parsed_data['type']
                
                if data_type == 'message':
                    # 收到消息内容
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True
                    
                    content = parsed_data.get('content', '')
                    if content:
                        # 更新性能统计
                        self._update_statistics(content)
                        
                        content_buffer.append(content)
                        display_buffer.append(content)
                        
                        # 检查内容长度，使用配置的限制
                        total_content_length = sum(len(c) for c in content_buffer)
                        if total_content_length > self.max_content_length:
                            logger.warning(f"响应内容过长: {total_content_length} 字符")
                            self.console.print(f"\n[yellow]⚠️ 响应内容超过限制 ({self.max_content_length} 字符)，已截断显示[/yellow]")
                            break
                        
                        # 应用速率限制
                        await self._apply_rate_limit()
                        
                        # 缓冲显示：累积一定量内容或遇到换行时显示
                        if len(display_buffer) >= buffer_size or '\n' in content:
                            # 显示缓冲的内容
                            buffered_content = ''.join(display_buffer)
                            self.console.print(buffered_content, end="", style="bright_white")
                            display_buffer.clear()
                            
                            # 小延迟提供更好的视觉效果
                            if self.delay_ms > 0:
                                await asyncio.sleep(self.delay_ms / 1000.0)
                    
                    # 更新消息和会话ID
                    if parsed_data.get('message_id'):
                        message_id = parsed_data['message_id']
                    if parsed_data.get('conversation_id'):
                        conversation_id = parsed_data['conversation_id']
                
                elif data_type == 'message_end':
                    # 消息结束
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True
                    
                    # 确保显示完整内容
                    final_content = parsed_data.get('content', '')
                    if final_content and final_content not in ''.join(content_buffer):
                        self.console.print(final_content, style="bright_white")
                    
                    # 更新最终的ID
                    if parsed_data.get('message_id'):
                        message_id = parsed_data['message_id']
                    if parsed_data.get('conversation_id'):
                        conversation_id = parsed_data['conversation_id']
                    
                    # 处理元数据
                    metadata = parsed_data.get('metadata', {})
                    if metadata:
                        self._display_metadata(metadata)
                    
                    break
                
                elif data_type == 'error':
                    # 处理错误
                    if show_typing:
                        status.stop()
                    
                    error_msg = parsed_data.get('error', 'Unknown error')
                    self.console.print(f"\n[red]错误: {error_msg}[/red]")
                    return None
                
                elif data_type == 'file':
                    # 处理文件消息
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True
                    
                    filename = parsed_data.get('filename', 'Unknown file')
                    self.console.print(f"\n[blue]📎 文件: {filename}[/blue]")
            
            # 确保停止状态显示
            if show_typing and not first_content_received:
                status.stop()
            
            # 显示剩余的缓冲内容
            if display_buffer:
                buffered_content = ''.join(display_buffer)
                self.console.print(buffered_content, end="", style="bright_white")
            
            # 如果有内容，确保换行
            if content_buffer:
                self.console.print()
                
                # 显示性能统计（借鉴 streaming_llm 的设计）
                stats = self._get_performance_stats()
                if stats:
                    try:
                        self.console.print(
                            f"[dim]✅ 响应完成 | "
                            f"{stats['elapsed_time']:.2f}s | "
                            f"{stats['total_chars']} 字符 | "
                            f"{stats['chars_per_second']:.1f} 字符/秒 | "
                            f"{stats['total_chunks']} 数据块[/dim]"
                        )
                    except Exception as stats_e:
                        logger.debug(f"显示性能统计失败: {stats_e}")
                        self.console.print(f"[dim]✅ 响应完成 (共 {len(content_buffer)} 个片段)[/dim]")
                else:
                    self.console.print(f"[dim]✅ 响应完成 (共 {len(content_buffer)} 个片段)[/dim]")
            
            # 缓存当前会话信息
            self._current_message_id = message_id
            self._current_conversation_id = conversation_id
            
            return conversation_id
            
        except Exception as e:
            if show_typing:
                try:
                    status.stop()
                except:
                    pass
            
            # 提供更详细的错误信息
            error_type = type(e).__name__
            error_msg = str(e)
            
            self.console.print(f"\n[red]流式输出处理错误 ({error_type}): {error_msg}[/red]")
            
            # 根据错误类型提供具体的解决建议
            if "ConnectionError" in error_type or "TimeoutError" in error_type:
                self.console.print("[yellow]建议: 检查网络连接或 Dify 服务状态[/yellow]")
            elif "JSONDecodeError" in error_type:
                self.console.print("[yellow]建议: Dify API 响应格式异常，请检查配置[/yellow]")
            elif "KeyError" in error_type:
                self.console.print("[yellow]建议: Dify API 响应字段缺失，可能是版本不兼容[/yellow]")
            else:
                self.console.print("[yellow]建议: 请检查 Dify 配置和网络连接[/yellow]")
            
            logger.error(f"流式输出处理错误: {error_type} - {error_msg}", exc_info=True)
            return None
    
    def _display_metadata(self, metadata: Dict[str, Any]):
        """
        显示元数据信息
        
        Args:
            metadata: 元数据字典
        """
        if 'usage' in metadata:
            usage = metadata['usage']
            self.console.print(f"\n[dim]Token使用: {usage}[/dim]")
        
        if 'retriever_resources' in metadata:
            resources = metadata['retriever_resources']
            if resources:
                self.console.print(f"\n[dim]引用资源: {len(resources)} 个[/dim]")
    
    async def display_simple_message(self, message: str, style: str = "bright_white"):
        """
        显示简单消息
        
        Args:
            message: 消息内容
            style: 消息样式
        """
        self.console.print(message, style=style)
    
    async def display_error(self, error: str):
        """
        显示错误消息
        
        Args:
            error: 错误信息
        """
        self.console.print(f"[red]错误: {error}[/red]")
    
    async def display_success(self, message: str):
        """
        显示成功消息
        
        Args:
            message: 成功信息
        """
        self.console.print(f"[green]{message}[/green]")
    
    async def display_info(self, message: str):
        """
        显示信息消息
        
        Args:
            message: 信息内容
        """
        self.console.print(f"[blue]{message}[/blue]")
    
    def get_current_conversation_id(self) -> Optional[str]:
        """
        获取当前会话ID
        
        Returns:
            当前会话ID，如果没有则返回None
        """
        return self._current_conversation_id
    
    def get_current_message_id(self) -> Optional[str]:
        """
        获取当前消息ID
        
        Returns:
            当前消息ID，如果没有则返回None
        """
        return self._current_message_id
