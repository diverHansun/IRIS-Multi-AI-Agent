"""
Gemini Agent Demo - 基于智谱AI的智能代理演示项目

这是一个使用LangChain框架和智谱AI的智能代理示例项目。
"""

__version__ = "1.0.0"
__author__ = "Gemini Agent Demo Team"

from .config import settings
from .agents.zhipu_agent import build_zhipu_agent, build_simple_zhipu_chat

__all__ = [
    "settings",
    "build_zhipu_agent", 
    "build_simple_zhipu_chat"
] 