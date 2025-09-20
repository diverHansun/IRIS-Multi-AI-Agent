"""
Dify 文件上传模块

处理文件上传功能，包括文件选择、验证和上传进度显示
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from rich.console import Console
from rich.progress import Progress, BarColumn, TimeRemainingColumn, FileSizeColumn, TotalFileSizeColumn
import logging

from .client import DifyClient, DifyClientError

logger = logging.getLogger(__name__)


class DifyUploader:
    """Dify 文件上传处理"""
    
    def __init__(self, client: DifyClient, console: Console, config: Dict[str, Any]):
        """
        初始化上传器
        
        Args:
            client: Dify 客户端实例
            console: Rich Console 实例
            config: 配置字典
        """
        self.client = client
        self.console = console
        self.config = config
        self.supported_types = set(config.get('supported_file_types', []))
        self.max_file_size = config.get('max_file_size', 10485760)  # 10MB
    
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        验证文件是否符合上传要求
        
        Args:
            file_path: 文件路径
            
        Returns:
            验证结果字典
        """
        if not os.path.exists(file_path):
            return {
                'valid': False,
                'error': f'文件不存在: {file_path}'
            }
        
        if not os.path.isfile(file_path):
            return {
                'valid': False,
                'error': f'不是有效文件: {file_path}'
            }
        
        # 检查文件扩展名
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in self.supported_types:
            supported_list = ', '.join(sorted(self.supported_types))
            return {
                'valid': False,
                'error': f'不支持的文件类型: {file_ext}\\n支持的类型: {supported_list}'
            }
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            max_size_mb = self.max_file_size / (1024 * 1024)
            current_size_mb = file_size / (1024 * 1024)
            return {
                'valid': False,
                'error': f'文件过大: {current_size_mb:.1f}MB > {max_size_mb:.1f}MB'
            }
        
        return {
            'valid': True,
            'size': file_size,
            'extension': file_ext
        }
    
    def select_file(self) -> Optional[str]:
        """
        显示文件选择对话框
        
        Returns:
            选择的文件路径，如果取消则返回None
        """
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.wm_attributes('-topmost', 1)  # 置顶显示
            
            # 构建文件类型过滤器
            filetypes = [
                ("所有支持的文件", " ".join(f"*{ext}" for ext in sorted(self.supported_types))),
                ("文档文件", "*.txt *.md *.markdown *.pdf *.html *.xlsx *.xls *.docx *.csv *.xml *.epub"),
                ("图片文件", "*.jpg *.jpeg *.png *.gif *.webp *.svg"),
                ("Office文件", "*.xlsx *.xls *.docx *.pptx *.ppt"),
                ("邮件文件", "*.eml *.msg"),
                ("所有文件", "*.*")
            ]
            
            file_path = filedialog.askopenfilename(
                title="选择要上传的文件",
                filetypes=filetypes,
                initialdir=os.getcwd()
            )
            
            root.destroy()
            
            return file_path if file_path else None
            
        except Exception as e:
            logger.error(f"文件选择对话框错误: {e}")
            self.console.print(f"[red]文件选择失败: {e}[/red]")
            return None
    
    async def upload_file(
        self, 
        file_path: str, 
        user_id: str,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        上传文件到 Dify
        
        Args:
            file_path: 文件路径
            user_id: 用户ID
            show_progress: 是否显示进度条
            
        Returns:
            上传结果
        """
        # 验证文件
        validation = self.validate_file(file_path)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error']
            }
        
        filename = os.path.basename(file_path)
        file_size = validation['size']
        
        try:
            if show_progress:
                # 显示上传进度
                with Progress(
                    "[progress.description]{task.description}",
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    FileSizeColumn(),
                    "->",
                    TotalFileSizeColumn(),
                    TimeRemainingColumn(),
                    console=self.console
                ) as progress:
                    task = progress.add_task(f"上传 {filename}", total=100)
                    
                    def progress_callback(percent):
                        progress.update(task, completed=percent)
                    
                    # 执行上传
                    result = await self.client.upload_file(
                        file_path, 
                        user_id, 
                        progress_callback=progress_callback
                    )
                    
                    progress.update(task, completed=100)
            else:
                # 不显示进度条
                result = await self.client.upload_file(file_path, user_id)
            
            return {
                'success': True,
                'file_id': result.get('id'),
                'filename': result.get('name', filename),
                'size': result.get('size', file_size),
                'type': result.get('type', 'file'),
                'raw_response': result  # 保留原始响应数据
            }
            
        except DifyClientError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"文件上传意外错误: {e}")
            return {
                'success': False,
                'error': f'上传失败: {e}'
            }
    
    async def upload_multiple_files(
        self, 
        file_paths: List[str], 
        user_id: str
    ) -> Dict[str, Any]:
        """
        批量上传文件
        
        Args:
            file_paths: 文件路径列表
            user_id: 用户ID
            
        Returns:
            批量上传结果
        """
        results = {
            'success': [],
            'failed': [],
            'total': len(file_paths)
        }
        
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("批量上传", total=len(file_paths))
            
            for i, file_path in enumerate(file_paths):
                filename = os.path.basename(file_path)
                progress.update(main_task, description=f"上传 {filename}")
                
                result = await self.upload_file(file_path, user_id, show_progress=False)
                
                if result['success']:
                    results['success'].append({
                        'file_path': file_path,
                        'result': result
                    })
                else:
                    results['failed'].append({
                        'file_path': file_path,
                        'error': result['error']
                    })
                
                progress.update(main_task, advance=1)
        
        return results


async def handle_upload_command(
    ctx, 
    query: str, 
    client: DifyClient, 
    console: Console, 
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    处理上传命令
    
    Args:
        ctx: 应用上下文
        query: 用户查询
        client: Dify 客户端
        console: Rich Console
        config: 配置字典
        
    Returns:
        处理结果
    """
    uploader = DifyUploader(client, console, config)
    parts = query.strip().split()
    
    if len(parts) < 2:
        # 没有指定文件路径，显示文件选择对话框
        console.print("[dim]正在打开文件选择对话框...[/dim]")
        file_path = uploader.select_file()
        
        if not file_path:
            console.print("[yellow]已取消上传[/yellow]")
            return {"type": "cancel"}
    else:
        # 使用命令行指定的文件路径
        file_path = " ".join(parts[1:])
        # 处理相对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
    
    # 验证文件
    validation = uploader.validate_file(file_path)
    if not validation['valid']:
        console.print(f"[red]{validation['error']}[/red]")
        return {"type": "error", "message": validation['error']}
    
    # 显示文件信息
    filename = os.path.basename(file_path)
    file_size_mb = validation['size'] / (1024 * 1024)
    console.print(f"[dim]准备上传: {filename} ({file_size_mb:.1f}MB)[/dim]")
    
    # 执行上传
    user_id = getattr(ctx, 'session_id', 'default_user')
    result = await uploader.upload_file(file_path, user_id)
    
    if result['success']:
        console.print(f"[green]✅ 上传成功: {result['filename']}[/green]")
        console.print(f"[dim]文件ID: {result['file_id']}[/dim]")
        
        # 如果是图片，显示额外信息
        if result.get('type') == 'image':
            console.print("[dim]💡 图片已上传，可在对话中引用[/dim]")
        else:
            console.print("[dim]📄 文档已上传，可在对话中引用[/dim]")
        
        return {
            "type": "success", 
            "file_id": result['file_id'],
            "filename": result['filename'],
            "file_type": result.get('type'),
            "file_info": result.get('raw_response', {})  # 包含完整的文件信息
        }
    else:
        console.print(f"[red]❌ 上传失败: {result['error']}[/red]")
        return {"type": "error", "message": result['error']}
