"""
Ollama 动态模型发现工具模块

提供统一的本机Ollama模型发现功能，支持HTTP API和CLI两种方式
遵循最小侵入原则，仅负责发现列表，不做任何选择策略
"""

import json
import logging
import shutil
import subprocess
import asyncio
from typing import List, Dict, Any

import aiohttp

from ...config import settings

logger = logging.getLogger(__name__)


async def get_ollama_models_http(base_url: str, timeout: int = 8) -> List[str]:
    """
    通过HTTP API获取Ollama模型列表
    
    Args:
        base_url: Ollama服务地址
        timeout: 请求超时时间（秒）
        
    Returns:
        List[str]: 模型名称列表，失败返回空列表
    """
    url = base_url.rstrip('/') + '/api/tags'
    
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            logger.debug(f"尝试HTTP获取Ollama模型: {url}")
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [
                        model.get('name') 
                        for model in data.get('models', []) 
                        if model.get('name')
                    ]
                    logger.info(f"HTTP方式获取到 {len(models)} 个Ollama模型")
                    logger.debug(f"HTTP模型列表: {models}")
                    return models
                else:
                    logger.warning(f"HTTP请求失败，状态码: {response.status}")
                    return []
                    
    except asyncio.TimeoutError:
        logger.warning(f"HTTP请求超时 ({timeout}秒): {url}")
        return []
    except aiohttp.ClientConnectorError:
        logger.debug("无法连接到Ollama服务，可能未启动")
        return []
    except Exception as e:
        logger.debug(f"HTTP请求异常: {str(e)}")
        return []


def get_ollama_models_cli() -> List[str]:
    """
    通过CLI命令获取Ollama模型列表
    
    Returns:
        List[str]: 模型名称列表，失败返回空列表
    """
    # 检查ollama命令是否存在
    if not shutil.which('ollama'):
        logger.debug("ollama CLI命令不存在")
        return []
        
    try:
        logger.debug("尝试CLI获取Ollama模型")
        
        # 执行ollama list --format json命令
        result = subprocess.run(
            ['ollama', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            # 解析JSON输出
            try:
                data = json.loads(result.stdout or '{}')
                models = [
                    model.get('name') 
                    for model in data.get('models', []) 
                    if model.get('name')
                ]
                logger.info(f"CLI方式获取到 {len(models)} 个Ollama模型")
                logger.debug(f"CLI模型列表: {models}")
                return models
            except json.JSONDecodeError as e:
                logger.warning(f"CLI输出JSON解析失败: {e}")
                # 尝试解析非JSON格式输出（兼容性处理）
                return _parse_ollama_list_text(result.stdout)
        else:
            logger.warning(f"CLI命令执行失败，返回码: {result.returncode}")
            logger.debug(f"CLI错误输出: {result.stderr}")
            return []
            
    except subprocess.TimeoutExpired:
        logger.warning("CLI命令执行超时")
        return []
    except Exception as e:
        logger.debug(f"CLI命令执行异常: {str(e)}")
        return []


def _parse_ollama_list_text(output: str) -> List[str]:
    """
    解析ollama list文本格式输出（兼容性处理）
    
    Args:
        output: ollama list的文本输出
        
    Returns:
        List[str]: 模型名称列表
    """
    models = []
    lines = output.strip().split('\n')
    
    for line in lines:
        # 跳过标题行和空行
        if not line.strip() or line.startswith('NAME'):
            continue
            
        # 提取模型名（第一列）
        parts = line.split()
        if parts:
            model_name = parts[0]
            if model_name and ':' in model_name:
                models.append(model_name)
    
    logger.debug(f"文本解析得到模型: {models}")
    return models


async def list_ollama_models(base_url: str = None, timeout: int = 8) -> List[str]:
    """
    获取本机可用的Ollama模型列表
    
    优先使用HTTP API，失败后回退到CLI命令
    
    Args:
        base_url: Ollama服务地址，默认使用配置中的地址
        timeout: HTTP请求超时时间（秒）
        
    Returns:
        List[str]: 模型名称列表，按发现顺序排序
    """
    if base_url is None:
        base_url = settings.ollama_base_url
    
    logger.debug(f"开始发现Ollama模型，base_url: {base_url}")
    
    # 方法1: 优先使用HTTP API
    models = await get_ollama_models_http(base_url, timeout)
    if models:
        logger.info(f"成功通过HTTP发现 {len(models)} 个模型")
        return models
    
    # 方法2: 回退到CLI命令
    logger.debug("HTTP方式失败，尝试CLI方式")
    models = get_ollama_models_cli()
    if models:
        logger.info(f"成功通过CLI发现 {len(models)} 个模型")
        return models
    
    # 两种方式都失败
    logger.info("未能发现任何Ollama模型")
    return []


def get_model_display_info(models: List[str]) -> List[Dict[str, Any]]:
    """
    为模型列表添加显示信息（用于CLI友好输出）
    
    Args:
        models: 模型名称列表
        
    Returns:
        List[Dict]: 包含显示信息的模型列表
    """
    model_info = []
    
    for model in models:
        info = {
            'name': model,
            'display_name': model,
            'description': _infer_model_description(model)
        }
        model_info.append(info)
    
    return model_info


def _infer_model_description(model_name: str) -> str:
    """
    基于模型名称推断描述信息
    
    Args:
        model_name: 模型名称
        
    Returns:
        str: 模型描述
    """
    name_lower = model_name.lower()
    
    # 中文优化模型
    if any(keyword in name_lower for keyword in ['qwen', 'chatglm', 'baichuan']):
        return "中文优化模型"
    
    # 代码专精模型  
    if any(keyword in name_lower for keyword in ['code', 'deepseek', 'starcoder']):
        return "代码专精模型"
    
    # 推理模型
    if any(keyword in name_lower for keyword in ['reasoning', 'think', 'r1']):
        return "推理专精模型"
    
    # 轻量模型
    if any(keyword in name_lower for keyword in ['mini', 'small', '1b', '3b']):
        return "轻量高效模型"
        
    # 大型模型
    if any(keyword in name_lower for keyword in ['20b', '70b', 'large']):
        return "大型通用模型"
    
    # 其他知名模型
    if 'gemma' in name_lower:
        return "Google Gemma模型"
    elif 'llama' in name_lower:
        return "Meta Llama模型"
    elif 'mistral' in name_lower:
        return "Mistral AI模型"
    
    return "通用对话模型"


# 便捷函数
async def discover_models() -> List[str]:
    """发现本机Ollama模型的便捷函数"""
    return await list_ollama_models()


def is_ollama_available() -> bool:
    """
    检查Ollama是否可用（同步版本，用于快速检测）
    
    Returns:
        bool: Ollama是否可用
    """
    return bool(shutil.which('ollama'))