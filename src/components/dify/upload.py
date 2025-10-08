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
        显示文件选择对话框（单文件）

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

    def select_files(self) -> Optional[List[str]]:
        """
        显示文件选择对话框（多文件）

        Returns:
            选择的文件路径列表，如果取消则返回None
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

            file_paths = filedialog.askopenfilenames(
                title="选择要上传的文件（可多选）",
                filetypes=filetypes,
                initialdir=os.getcwd()
            )

            root.destroy()

            return list(file_paths) if file_paths else None

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
        批量上传文件（带详细进度显示）

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

        # 计算总大小
        total_size = 0
        for file_path in file_paths:
            try:
                total_size += os.path.getsize(file_path)
            except:
                pass

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

            # 主任务：整体进度
            main_task = progress.add_task(
                f"批量上传 (0/{len(file_paths)})",
                total=total_size if total_size > 0 else len(file_paths)
            )

            uploaded_size = 0

            for i, file_path in enumerate(file_paths, 1):
                filename = os.path.basename(file_path)

                # 更新主任务描述
                progress.update(
                    main_task,
                    description=f"批量上传 ({i}/{len(file_paths)}) - {filename}"
                )

                # 上传文件
                result = await self.upload_file(file_path, user_id, show_progress=False)

                if result['success']:
                    results['success'].append({
                        'file_path': file_path,
                        'result': result
                    })
                    # 更新已上传大小
                    try:
                        file_size = os.path.getsize(file_path)
                        uploaded_size += file_size
                    except:
                        pass
                else:
                    results['failed'].append({
                        'file_path': file_path,
                        'error': result['error']
                    })

                # 更新进度
                if total_size > 0:
                    progress.update(main_task, completed=uploaded_size)
                else:
                    progress.update(main_task, advance=1)

            # 完成
            progress.update(
                main_task,
                description=f"批量上传完成 - 成功: {len(results['success'])}, 失败: {len(results['failed'])}",
                completed=total_size if total_size > 0 else len(file_paths)
            )

        return results


async def handle_upload_command(
    ctx,
    query: str,
    client: DifyClient,
    console: Console,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    处理上传命令（支持单文件和多文件）

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

    file_paths = []

    if len(parts) < 2:
        # 没有指定文件路径，显示文件选择对话框（支持多选）
        console.print("[dim]正在打开文件选择对话框（支持多选）...[/dim]")
        selected_paths = uploader.select_files()

        if not selected_paths:
            console.print("[yellow]已取消上传[/yellow]")
            return {"type": "cancel"}

        file_paths = selected_paths
    else:
        # 使用命令行指定的文件路径（支持空格分隔的多个路径）
        for i in range(1, len(parts)):
            file_path = parts[i]
            # 处理相对路径
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)
            file_paths.append(file_path)

    # 单文件上传
    if len(file_paths) == 1:
        file_path = file_paths[0]

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
            console.print(f"[green]上传成功: {result['filename']}[/green]")
            console.print(f"[dim]文件ID: {result['file_id']}[/dim]")

            # 如果是图片，显示额外信息
            if result.get('type') == 'image':
                console.print("[dim]提示: 图片已上传，可在对话中引用[/dim]")
            else:
                console.print("[dim]提示: 文档已上传，可在对话中引用[/dim]")

            return {
                "type": "success",
                "file_id": result['file_id'],
                "filename": result['filename'],
                "file_type": result.get('type'),
                "file_info": result.get('raw_response', {}),  # 包含完整的文件信息
                "uploaded_files": [result]  # 统一返回格式
            }
        else:
            console.print(f"[red]上传失败: {result['error']}[/red]")
            return {"type": "error", "message": result['error']}

    # 多文件批量上传
    else:
        console.print(f"[blue]准备批量上传 {len(file_paths)} 个文件...[/blue]")

        # 先验证所有文件
        valid_files = []
        invalid_files = []

        for file_path in file_paths:
            validation = uploader.validate_file(file_path)
            if validation['valid']:
                valid_files.append(file_path)
            else:
                invalid_files.append({
                    'path': file_path,
                    'error': validation['error']
                })

        # 显示验证结果
        if invalid_files:
            console.print(f"[yellow]警告: {len(invalid_files)} 个文件验证失败，将被跳过：[/yellow]")
            for item in invalid_files:
                console.print(f"  [dim]{os.path.basename(item['path'])}: {item['error']}[/dim]")

        if not valid_files:
            console.print("[red]没有有效的文件可上传[/red]")
            return {"type": "error", "message": "所有文件验证失败"}

        console.print(f"[dim]开始上传 {len(valid_files)} 个有效文件...[/dim]")

        # 执行批量上传
        user_id = getattr(ctx, 'session_id', 'default_user')
        batch_result = await uploader.upload_multiple_files(valid_files, user_id)

        # 显示结果汇总
        success_count = len(batch_result['success'])
        failed_count = len(batch_result['failed'])

        if success_count > 0:
            console.print(f"[green]成功上传 {success_count} 个文件[/green]")
            for item in batch_result['success']:
                filename = item['result']['filename']
                file_id = item['result']['file_id']
                console.print(f"  [dim]• {filename} (ID: {file_id})[/dim]")

        if failed_count > 0:
            console.print(f"[red]{failed_count} 个文件上传失败[/red]")
            for item in batch_result['failed']:
                filename = os.path.basename(item['file_path'])
                console.print(f"  [dim]• {filename}: {item['error']}[/dim]")

        # 返回批量上传结果
        if success_count > 0:
            return {
                "type": "success",
                "uploaded_files": [item['result'] for item in batch_result['success']],
                "success_count": success_count,
                "failed_count": failed_count,
                "batch_result": batch_result
            }
        else:
            return {
                "type": "error",
                "message": f"所有文件上传失败",
                "failed_count": failed_count,
                "batch_result": batch_result
            }
