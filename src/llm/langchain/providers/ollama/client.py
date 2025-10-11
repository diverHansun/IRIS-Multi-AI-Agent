#!/usr/bin/env python3
"""
Ollama HTTP Client - Direct HTTP implementation, bypassing LangChain 502 issues
"""

import json
import asyncio
import aiohttp
import logging
from typing import AsyncGenerator, Optional, Dict, Any

logger = logging.getLogger(__name__)

class OllamaClient:
    """Direct HTTP client for Ollama API, bypassing LangChain issues"""
    
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
    async def stream_chat(
        self, 
        model: str, 
        prompt: str,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        """
        直接HTTP流式聊天，绕过LangChain
        
        Args:
            model: 模型名称
            prompt: 用户输入
            temperature: 温度参数
            
        Yields:
            str: 流式响应内容
        """
        logger.info(f"[HTTP_CLIENT] 开始直接HTTP流式请求")
        logger.info(f"[HTTP_CLIENT] 模型: {model}, 提示长度: {len(prompt)}")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40
            }
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.info(f"[HTTP_CLIENT] 发送请求到 {self.base_url}/api/chat")
                
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    logger.info(f"[HTTP_CLIENT] HTTP状态: {response.status}")
                    
                    if response.status == 200:
                        chunk_count = 0
                        async for line in response.content:
                            if line:
                                try:
                                    line_str = line.decode('utf-8').strip()
                                    if line_str:
                                        data = json.loads(line_str)
                                        
                                        # 提取消息内容
                                        if 'message' in data and 'content' in data['message']:
                                            content = data['message']['content']
                                            if content:
                                                chunk_count += 1
                                                logger.debug(f"[HTTP_CLIENT] Chunk #{chunk_count}: {content[:30]}...")
                                                yield content
                                        
                                        # 检查是否完成
                                        if data.get('done', False):
                                            logger.info(f"[HTTP_CLIENT] 流式完成，共 {chunk_count} chunks")
                                            break
                                            
                                except json.JSONDecodeError:
                                    continue
                                except Exception as chunk_e:
                                    logger.warning(f"[HTTP_CLIENT] 解析chunk失败: {chunk_e}")
                                    continue
                        
                        if chunk_count == 0:
                            yield "HTTP客户端收到空响应"
                            
                    else:
                        error_text = await response.text()
                        logger.error(f"[HTTP_CLIENT] HTTP错误 {response.status}: {error_text}")
                        raise Exception(f"HTTP {response.status}: {error_text}")
                        
        except asyncio.TimeoutError:
            logger.error(f"[HTTP_CLIENT] 请求超时 ({self.timeout}s)")
            raise Exception(f"HTTP请求超时 ({self.timeout}s)")
        except Exception as e:
            logger.error(f"[HTTP_CLIENT] 请求异常: {e}")
            raise

    async def simple_chat(self, model: str, prompt: str, temperature: float = 0.1) -> str:
        """
        简单非流式聊天
        
        Args:
            model: 模型名称
            prompt: 用户输入
            temperature: 温度参数
            
        Returns:
            str: 完整响应
        """
        logger.info(f"[HTTP_CLIENT] 简单聊天请求")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40
            }
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        if 'message' in data and 'content' in data['message']:
                            return data['message']['content']
                        else:
                            return "收到响应但无内容"
                    else:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"[HTTP_CLIENT] 简单聊天失败: {e}")
            raise

    async def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except:
            return False