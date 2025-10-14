"""
Dify API 客户端

提供与 Dify 平台的基础 API 交互功能
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List
import aiohttp
import logging

logger = logging.getLogger(__name__)


class DifyClientError(Exception):
    """Dify 客户端异常"""
    pass


class DifyClient:
    """Dify API 客户端"""
    
    def __init__(self, api_key: str, base_url: str, timeout: int = 30):
        """
        初始化 Dify 客户端
        
        Args:
            api_key: Dify API 密钥（包含应用信息）
            base_url: API 基础URL
            timeout: 请求超时时间
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.streaming_timeout = timeout * 4  # 流式请求使用更长的超时时间
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self._session = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._session:
            await self._session.close()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        # 检查会话是否存在且未关闭
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: 请求参数
            
        Returns:
            响应数据
            
        Raises:
            DifyClientError: 请求失败时抛出
        """
        url = f"{self.base_url}/{endpoint}"
        session = await self._get_session()
        
        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise DifyClientError(f"API请求失败: {response.status}, {error_text}")
        except aiohttp.ClientError as e:
            raise DifyClientError(f"网络请求错误: {str(e)}")
        except json.JSONDecodeError as e:
            raise DifyClientError(f"响应解析错误: {str(e)}")
    
    async def chat_message(
        self, 
        query: str, 
        user_id: str, 
        streaming: bool = True,
        conversation_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        files: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送聊天消息
        
        Args:
            query: 用户查询
            user_id: 用户ID
            streaming: 是否流式输出
            conversation_id: 会话ID（可选）
            inputs: 输入参数（可选）
            files: 文件列表（可选）
            
        Yields:
            流式响应数据
            
        Raises:
            DifyClientError: 请求失败时抛出
        """
        url = f"{self.base_url}/chat-messages"
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "streaming" if streaming else "blocking",
            "user": user_id
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
            
        if files:
            payload["files"] = files
        
        session = await self._get_session()
        
        try:
            # 流式请求使用更长的超时时间
            timeout = aiohttp.ClientTimeout(total=self.streaming_timeout)
            async with session.post(url, json=payload, headers=self.headers, timeout=timeout) as response:
                if response.status != 200:
                    error_text = await response.text()
                    # 尝试解析错误信息获取更详细的内容
                    try:
                        error_json = json.loads(error_text)
                        error_message = error_json.get('message', error_text)
                        error_code = error_json.get('code', 'unknown')
                        logger.error(f"Dify API错误 - 状态码: {response.status}, 错误码: {error_code}, 消息: {error_message}")
                        raise DifyClientError(f"聊天请求失败 [{error_code}]: {error_message}")
                    except json.JSONDecodeError:
                        logger.error(f"Dify API错误 - 状态码: {response.status}, 原始响应: {error_text}")
                        raise DifyClientError(f"聊天请求失败: {response.status}, {error_text}")
                
                if streaming:
                    # 处理流式响应，使用缓冲机制减少处理频率
                    buffer = b''
                    async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                        buffer += chunk
                        
                        # 按行分割数据
                        while b'\n' in buffer:
                            line, buffer = buffer.split(b'\n', 1)
                            
                            if line.startswith(b'data: '):
                                try:
                                    data = json.loads(line[6:].decode('utf-8'))
                                    yield data
                                except json.JSONDecodeError:
                                    logger.warning(f"无法解析流式数据: {line}")
                                    continue
                else:
                    # 处理阻塞式响应
                    result = await response.json()
                    yield result
                    
        except aiohttp.ClientError as e:
            raise DifyClientError(f"聊天请求网络错误: {str(e)}")
    
    async def upload_file(
        self, 
        file_path: str, 
        user_id: str, 
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        上传文件到 Dify
        
        Args:
            file_path: 文件路径
            user_id: 用户ID
            progress_callback: 进度回调函数
            
        Returns:
            上传结果
            
        Raises:
            DifyClientError: 上传失败时抛出
        """
        if not os.path.exists(file_path):
            raise DifyClientError(f"文件不存在: {file_path}")
        
        url = f"{self.base_url}/files/upload"
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # 判断文件类型和 MIME 类型
        file_ext = os.path.splitext(filename)[1].lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg', 
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        content_type = mime_type_map.get(file_ext, 'application/octet-stream')
        
        session = await self._get_session()
        
        # 使用with语句确保文件正确关闭
        try:
            with open(file_path, 'rb') as file_obj:
                # 创建表单数据（根据 API 文档只需要 file 和 user 字段）
                data = aiohttp.FormData()
                data.add_field('file',
                              file_obj,
                              filename=filename,
                              content_type=content_type)
                data.add_field('user', user_id)

                # 上传文件
                headers = {"Authorization": f"Bearer {self.api_key}"}
                async with session.post(url, data=data, headers=headers) as response:
                    if response.status in (200, 201):  # 200 OK 或 201 Created 都表示成功
                        result = await response.json()
                        if progress_callback:
                            progress_callback(100)  # 完成
                        return result
                    else:
                        error_text = await response.text()
                        error_message = self._parse_upload_error(response.status, error_text)
                        raise DifyClientError(error_message)

        except aiohttp.ClientError as e:
            raise DifyClientError(f"文件上传网络错误: {str(e)}")
        except OSError as e:
            raise DifyClientError(f"文件读取错误: {str(e)}")
    
    def _parse_upload_error(self, status_code: int, error_text: str) -> str:
        """
        解析上传错误，提供友好的错误信息
        
        Args:
            status_code: HTTP状态码
            error_text: 错误响应文本
            
        Returns:
            友好的错误信息
        """
        try:
            error_data = json.loads(error_text)
            error_code = error_data.get('code', '')
        except:
            error_code = ''
        
        # 根据状态码和错误代码提供友好提示
        error_messages = {
            400: {
                'no_file_uploaded': '必须提供文件',
                'too_many_files': '目前只接受一个文件',
                'unsupported_preview': '该文件不支持预览',
                'unsupported_estimate': '该文件不支持估算',
                '': '请求参数错误'
            },
            413: {
                'file_too_large': '文件太大，请选择较小的文件',
                '': '文件太大'
            },
            415: {
                'unsupported_file_type': '不支持的文件类型，当前只接受文档类文件',
                '': '不支持的文件类型'
            },
            503: {
                's3_connection_failed': '无法连接到存储服务',
                's3_permission_denied': '无权限上传文件',
                's3_file_too_large': '文件超出存储服务大小限制',
                '': '服务暂时不可用'
            }
        }
        
        if status_code in error_messages:
            message = error_messages[status_code].get(error_code, 
                                                    error_messages[status_code][''])
            return f"文件上传失败: {message} (状态码: {status_code})"
        else:
            return f"文件上传失败: {status_code}, {error_text}"

    async def close(self):
        """关闭客户端并清理资源"""
        try:
            if self._session and not self._session.closed:
                # 取消所有挂起的请求
                await self._session.close()
                # 等待连接器清理完成
                await asyncio.sleep(0.1)
                self._session = None
                logger.debug("Dify client session closed successfully")
        except Exception as e:
            logger.warning(f"Error during client session close: {e}")
            self._session = None
